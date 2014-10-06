#!/usr/bin/env python

from flask import render_template

from ioos_catalog import app, db

@app.route('/', methods=['GET'])
def index():
    return landing()

@app.route('/landing', methods=['GET'])
@app.route('/landing/', methods=['GET'])
def landing():
    total_datasets = db.Dataset.total_datasets()
    total_services = db.Service.find({"active":True}).count()
    return render_template('landing.html', total_datasets=total_datasets, total_services=total_services)

