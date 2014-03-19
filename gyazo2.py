#!/usr/bin/env python2
# Copyright (C) 2014 Yuto Kawamura
# This software is released under the MIT License.
# Author: Yuto Kawamura(kawamuray) <kawamuray.dadada {at} gmail.com>
import signal, os, sys, subprocess, tempfile, time, urllib2
from Xlib import X, Xcursorfont
from Xlib import display as Xdisplay

VERSION = 0.02

# Configurations
GYAZO_URI      = 'http://gyazo.com/upload.cgi'
GYAZOGIF_URI   = 'http://gif.gyazo.com/'
GIFZO_URI      = 'http://gifzo.net/'
GYAZO_IDFILE   = os.environ['HOME'] + '/.gyazo.id'
#                 'r'      Alt     == Alt + r
REC_TOGGLE_KEY = (0x1b, X.Mod1Mask) # Toggle video capture keycode
OPEN_CMD       = 'firefox' # Browser command to open url(None to disable)
CLIP_CMD       = 'xclip'   # Clipboard command(None to disable)
DEFAULT_MODE   = 'gyazo'   # Fallback if couldn't detect from argv[0]
DEBUG          = False


class RectangleFrame:
    def __init__(self, display, foreground, background):
        self.display = display
        self.rootwin = self.display.screen().root
        self.gc = self.rootwin.create_gc(
            foreground     = foreground,
            background     = background,
            function       = X.GXinvert,
            plane_mask     = background ^ foreground,
            subwindow_mode = X.IncludeInferiors,
        )

    def draw(self, x, y, width, height):
        self.rootwin.rectangle(self.gc, x, y, width, height)
        self.display.flush()

    def destroy(self):
        self.display.flush()
        self.gc.free()

class XEventQueue:
    def __init__(self, source):
        self.source = source
        self.headevent = None

    def has_more(self):
        True if self.source.pending_events() else False

    def head(self):
        if not self.headevent:
            self.headevent = self.next()

        return self.headevent
            
    def next(self):
        if self.headevent:
            ev = self.headevent
            self.headevent = None
        else:
            ev = self.source.next_event()

        return ev

def makecursor(display):
    font = display.open_font('cursor')
    cursor_type = Xcursorfont.cross
    cursor = font.create_glyph_cursor(font, cursor_type, cursor_type + 1,
                                      (0, 0, 0), (0xFFFF, 0xFFFF, 0xFFFF))
    font.close()
    return cursor

def reposition(basep, cropp):
    if cropp > basep:
        basep, cropp = cropp, basep

    return (cropp, basep - cropp)

def getgeometry(dispnum):
    display = Xdisplay.Display(dispnum)
    screen = display.screen()
    rootwin = screen.root
    rectfrm = RectangleFrame(display, screen.white_pixel, screen.black_pixel)
    cursor = makecursor(display)
    status = rootwin.grab_pointer(
        False, (X.ButtonPressMask|X.ButtonReleaseMask|X.ButtonMotionMask),
        X.GrabModeSync, X.GrabModeAsync, rootwin, cursor, X.CurrentTime
    )
    if status != X.GrabSuccess:
        return None

    base_x, base_y = 0, 0
    crop_x, crop_y = 0, 0
    crop_width, crop_height = 0, 0
    presscount = 0
    evq = XEventQueue(display)

    while True:
        if crop_width > 0 and crop_height > 0:
            rectfrm.draw(crop_x, crop_y, crop_width - 1, crop_height - 1)

        display.allow_events(X.SyncPointer, X.CurrentTime)
        ev = evq.next()

        # Hide rectangle frame to prepare for next rendering
        if crop_width > 0 and crop_height > 0:
            rectfrm.draw(crop_x, crop_y, crop_width - 1, crop_height - 1)

        if ev.type == X.ButtonPress:
            crop_x = base_x = ev.root_x
            crop_y = base_y = ev.root_y
            crop_width = 0
            crop_height = 0
            presscount += 1
        elif ev.type == X.ButtonRelease:
            presscount -= 1
        elif ev.type == X.MotionNotify:
            # Discard pending button motion events
            while evq.has_more() and evq.head() & X.ButtonMotionMask:
                ev = evq.next()

            crop_x, crop_width = reposition(base_x, ev.event_x)
            crop_y, crop_height = reposition(base_y, ev.event_y)

        if presscount <= 0: break

    display.ungrab_pointer(X.CurrentTime)
    cursor.free()
    rectfrm.destroy()
    display.close()

    return (crop_x, crop_y, crop_width, crop_height)

class XScreenCapture:
    devnull = open(os.devnull, 'w')
    framerate = 25
    blinkingframe_interval = 0.3

    def __init__(self, outpath, dispnum = ':0.0', debug = False):
        self.outpath = outpath
        self.dispnum = dispnum
        self.debug = debug
        self.child = None

    def start(self, geom):
        if self.child: # Already running
            return 0
        else:
            prfd, pwfd = os.pipe()
            pid = os.fork()
            if pid == 0:
                os.close(pwfd)
                self.spawn_recorder(prfd, *geom)
            else:
                os.close(prfd)
                self.child = {
                    'pid':   pid,
                    'stdin': pwfd,
                }
            return pid

    def spawn_recorder(self, stdin, x, y, width, height):
        capture_geometry = '%s+%d,%d' % (self.dispnum, x, y)
        capture_size = '%dx%d' % (width, height)

        ffmpeg = subprocess.Popen(
            [
                'ffmpeg',
                '-y',                               # Allow overwrite
                '-f',          'x11grab',           # Input format
                '-framerate',  str(self.framerate), # Frame per sec
                '-video_size', capture_size,
                '-i',          capture_geometry,
                self.outpath                        # Output file
            ],
            stdin = stdin,
            stderr = sys.stderr if self.debug else self.devnull,
        )

        # Show blinking frame while recording display
        display = Xdisplay.Display(self.dispnum)
        frame = RectangleFrame(display, 0xFFFFFF, 0x000000)

        flip = False
        while ffmpeg.poll() is None:
            frame.draw(x - 1, y - 1, width + 1, height + 1)
            time.sleep(self.blinkingframe_interval)
            flip = not flip
        if flip:
            # Cleanup frame
            frame.draw(x - 1, y - 1, width + 1, height + 1)

        frame.destroy()
        display.close()

        sys.exit(ffmpeg.wait())

    def stop(self):
        if self.child:
            # Terminate ffmpeg by sending 'q'
            fd = self.child['stdin']
            os.write(fd, 'q')
            os.close(fd)
            status = os.waitpid(self.child['pid'], 0)
            self.child = None
            return status
        else:
            return None

class ScreenRecorderGuard:
    def __init__(self, togglekey = None, dispnum = ':0.0'):
        self.togglekey = togglekey
        self.dispnum = dispnum
        self.escaped = False

    def wait_keyboard(self):
        keycode, mod = self.togglekey
        display = Xdisplay.Display(self.dispnum)

        display.screen().root.grab_key(
            key           = keycode,
            modifiers     = mod,
            owner_events  = False,
            pointer_mode  = X.GrabModeAsync,
            keyboard_mode = X.GrabModeAsync,
        )

        pressed = False
        while not self.escaped:
            while display.pending_events():
                ev = display.next_event()
                if ev.type == X.KeyPress:
                    pressed = True
                elif ev.type == X.KeyRelease:
                    if pressed:
                        self.escaped = True
                        break
            time.sleep(0.001)

        display.screen().root.ungrab_key(keycode, mod)
        display.close()

    def wait_start(self):
        self.escaped = False
        if self.togglekey:
            self.wait_keyboard()

    def sighandle(self, a, b):
        self.escaped = True

    def wait_finish(self):
        self.escaped = False
        signal.signal(signal.SIGINT, self.sighandle)
        if self.togglekey:
            self.wait_keyboard()
        else:
            while not self.escaped:
                signal.pause()

def capture_png():
    fd, tmpfile = tempfile.mkstemp(suffix = '.png')
    os.close(fd)

    subprocess.call(['import', tmpfile])

    return tmpfile

def capture_mp4():
    fd, tmpfile = tempfile.mkstemp(suffix = '.mp4')
    os.close(fd)

    xdisp = os.getenv('DISPLAY', ':0.0')
    geometry = getgeometry(xdisp)
    if not geometry:
        sys.exit("Can't get geometry from %s" % xdisp)
    xcapt = XScreenCapture(tmpfile, xdisp, debug = DEBUG)
    guard = ScreenRecorderGuard(
        togglekey = REC_TOGGLE_KEY,
        dispnum   = xdisp,
    )
    guard.wait_start()
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    xcapt.start(geometry)
    sys.stderr.write("Ctrl-C to stop recording\n")
    guard.wait_finish()
    xcapt.stop()

    return tmpfile

UPLOAD_CONFIG = {
    'gyazo': {
        'uri':      GYAZO_URI,
        'name':     'imagedata',
        'filename': 'gyazo.com',
        'ua':       'Gyazo2.0Linux/%d' % VERSION,
        'capture':  capture_png,
    },
    'gyazogif': {
        'uri':      GYAZOGIF_URI,
        'name':     'data',
        'filename': 'gyazo.mp4',
        'ua':       'Gyazo-GIFLinux/%d' % VERSION,
        'capture':  capture_mp4,
    },
    'gifzo': {
        'uri':      GIFZO_URI,
        'name':     'data',
        'filename': 'gifzo.mp4',
        'ua':       'GifzoLinux/%d' % VERSION,
        'capture':  capture_mp4,
    },
}

# main
mode = os.path.basename(sys.argv[0])
if not mode in UPLOAD_CONFIG:
    mode = DEFAULT_MODE # fallback

config = UPLOAD_CONFIG[mode]
tmpfile = config['capture']()

boundary = '------BOUNDARYYYYYYYYYYYYYYY-------'
with open(tmpfile, 'r') as f:
    formdata = """\
--%(boundary)s\r
Content-Disposition: form-data; name="%(name)s"; filename="%(filename)s"\r
Content-Type: application/octet-stream\r
\r
%(imgdata)s\r
""" % {
        'boundary': boundary,
        'name':     config['name'],
        'filename': config['filename'],
        'imgdata':  f.read(),
    }

gyazoid = None
if mode.startswith('gyazo') and os.path.isfile(GYAZO_IDFILE):
    with open(GYAZO_IDFILE, 'r') as f:
        gyazoid = f.read().rstrip('rn')
    if gyazoid:
        formdata += """\
--%s\r
Content-Disposition: form-data; name="id"\r
\r
%s\r
""" % (boundary, gyazoid)

formdata += "--%s--\r\n" % boundary # Terminate multipart/form-data

req = urllib2.Request(config['uri'], formdata, {
    'Content-Type':  'multipart/form-data; boundary=%s' % boundary,
    'User-Agent':    config['ua'],
})
try:
    res = urllib2.urlopen(req)
except urllib2.URLError as e:
    sys.exit("Failed to upload image %s : %s" % (config['uri'], e))

openurl = res.read().rstrip('rn')
sys.stdout.write(openurl + "\n")

# Copy returned url to clipboard
if CLIP_CMD:
    try:
        clipper = subprocess.Popen([CLIP_CMD], stdin = subprocess.PIPE)
    except Exception as e:
        sys.stderr.write("%s: Can't exec %s : %s." % (sys.argv[0], CLIP_CMD, e)
                         + " Please change CLIP_CMD to None"
                         + " if you don't need to copy url to clipboard")
    else:
        clipper.stdin.write(openurl)
        clipper.stdin.close()
        clipper.wait()

# Open returned url in specified command
if OPEN_CMD:
    try:
        subprocess.call([OPEN_CMD, openurl])
    except Exception as e:
        sys.stderr.write("%s: Can't exec %s : %s." % (sys.argv[0], OPEN_CMD, e)
                         + " Please change OPEN_CMD to None"
                         + " if you don't need to open url")

# Write Gyazo ID to file
if not(gyazoid) and mode.startswith('gyazo') and GYAZO_IDFILE:
    gyazoid = res.headers.getheader('X-Gyazo-Id')
    if gyazoid:
        with open(GYAZO_IDFILE, 'w') as f:
            f.write(gyazoid)
