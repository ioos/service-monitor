#!/usr/bin/env python
'''
Tasks relating to the managment of the CAPTCHA cache and database
'''

from ioos_catalog import app
from ioos_catalog import captcha

def initialize_captcha_db():
    with app.app_context():
        captcha.ext_db.create_all()
        app.logger.info("Captcha DB Initialized")

