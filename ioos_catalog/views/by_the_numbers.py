#!/usr/bin/env python
from flask import render_template

from ioos_catalog import app

@app.route('/by_the_numbers', methods=['GET'])
@app.route('/by_the_numbers/', methods=['GET'])
def by_the_numbers():
    return render_template('by_the_numbers.html')

