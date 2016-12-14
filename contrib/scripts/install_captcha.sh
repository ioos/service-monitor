#!/bin/bash

cd /opt
git clone https://github.com/rickmer/flask-captcha --depth=1
cd flask-captcha
python setup.py install
cp /opt/flask-captcha/flask_captcha/fonts/Vera.ttf /usr/lib/python2.7/site-packages/Flask_Captcha-0.1.8-py2.7.egg/flask_captcha/fonts/Vera.ttf
