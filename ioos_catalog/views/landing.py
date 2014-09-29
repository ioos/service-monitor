#!/usr/bin/env python

from flask import render_template

from ioos_catalog import app

@app.route('/', methods=['GET'])
def index():
    return landing()

@app.route('/landing', methods=['GET'])
@app.route('/landing/', methods=['GET'])
def landing():
    return render_template('landing.html')
