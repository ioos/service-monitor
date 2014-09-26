#!/usr/bin/env python

from ioos_catalog import app
from flask import render_template

@app.route('/featured_maps', methods=['GET'])
@app.route('/featured_maps/', methods=['GET'])
def featured_maps():
    return render_template('featured_maps.html')

