#!/usr/bin/env python
from flask import render_template
from ioos_catalog import app

@app.route('/gliders', methods=['GET'])
def gliders():
    return render_template('gliders.html')

