#!/usr/bin/env python
#-*- coding: utf-8 -*-
'''
tests/test_email.py
'''

from tests.flask_mongo import FlaskMongoTestCase
from ioos_catalog.views.help import prepare_email

class TestEmail(FlaskMongoTestCase):
    def test_email(self):
        with self.raw_app.app_context():
            prepare_email('Luke Campbell', 'luke.campbell@rpsgroup.com', 'Test Email')

