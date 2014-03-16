About
=====
This is an *unofficial* [Gyazo](https://gyazo.com/) client for Linux.  This software supports Gyazo2.0 feature(GIF support) and also able to behave as [Gifzo](http://gifzo.net/) client.
More strictly, this is Gyazo/Gifzo client for desktop which working on top of X Window System. This client won't be work on other window systems.

Requirements
============
- python2.6
- [python-Xlib >= 0.12](https://pypi.python.org/pypi/python-xlib)
- [import](http://www.imagemagick.org/script/import.php)(from ImageMagick, if you want Gyazo support)
- [ffmpeg](http://www.ffmpeg.org/)(with x11grab support, if you want GyazoGIF or Gifzo support)

Install
=======
Here's basic example of procedure to install.  Ofcourse you can change the install location to where you like.

    # Install python-Xlib(if you already havn't)
    sudo pip install 'http://sourceforge.net/projects/python-xlib/files/latest/download?source=files'
    # Install gyazo command
    curl https://raw.github.com/kawamuray/Gyazo2-Gifzo-Linux/master/gyazo2.py | sudo tee /usr/local/bin/gyazo >/dev/null
    sudo chmod +x /usr/local/bin/gyazo
    # Optionally support GyazoGIF
    sudo ln -s /usr/local/bin/gyazo /usr/local/bin/gyazogif
    # Optionally support Gifzo
    sudo ln -s /usr/local/bin/gyazo /usr/local/bin/gifzo

Configuration
=============
Take a look at head of gyazo2.py.

Author
======
Yuto KAWAMURA(kawamuray) kawamuray.dadada {at} gmail.com

License
=======
The MIT License(MIT)

Copyright (C) 2014 Yuto KAWAMURA
