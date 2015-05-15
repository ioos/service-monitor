#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
ioos_catalog/views/metrics.py
'''

from ioos_catalog import app, db
from bson import json_util
from flask import jsonify, render_template, url_for, request
from glob import glob
from ioos_catalog.views.ra import provider_info as p_info
from collections import OrderedDict
from StringIO import StringIO
import json
import pymongo
import csv

@app.route('/api/metrics', methods=['GET'])
def get_metrics():
    start = request.args.get('start', 0)
    stop = request.args.get('stop', 100)
    results = []
    try:
        for doc in db.MetricCount.find({}).sort("date",pymongo.DESCENDING)[start:stop]:
            results.append(doc)

        json_doc = json.dumps({"results":results}, default=json_util.default)
    except Exception as e:
        return jsonify(error=e.message), 400
    return json_doc, 200, {'Content-Type':'application/json'}

@app.route('/csv/metrics/datasets_by_ra', methods=['GET'])
def get_csv_metrics_by_ra():
    start = request.args.get('start', 0)
    stop = request.args.get('stop', 100)
    results = []
    results.append(['date', 'provider', 'active_services', 'inactive_services', 'total_services'])
    try:
        for doc in db.MetricCount.find({"stats_type":"datasets_by_ra"}).sort("date",pymongo.DESCENDING)[start:stop]:
            for record in doc.count:
                row = []
                row.append(doc.date.isoformat())
                row.append(record['_id'])
                row.append(record['active_services'])
                row.append(record['inactive_services'])
                row.append(record['total_services'])
                results.append(row)
            #row.append(doc.date.isoformat(), 
    except Exception as e:
        raise
        return "Error: %s" % e.message, 400, {'Content-Type':'text/plain'}
    buf = StringIO()
    csvwriter = csv.writer(buf)
    for row in results:
        csvwriter.writerow(row)
    buf.seek(0)
    buf = buf.read()
    return buf, 200, {'Content-Type':'text/csv'}

@app.route('/csv/metrics/services_by_type', methods=['GET'])
def get_csv_metrics_by_type():
    start = request.args.get('start', 0)
    stop = request.args.get('stop', 100)
    results = []
    results.append(['date', 'service_type', 'active_count', 'inactive_count', 'count'])
    try:
        for doc in db.MetricCount.find({"stats_type":"services_by_type"}).sort("date",pymongo.DESCENDING)[start:stop]:
            for record in doc.count:
                row = []
                row.append(doc.date.isoformat())
                row.append(record['_id'])
                row.append(record['active_count'])
                row.append(record['inactive_count'])
                row.append(record['count'])
                results.append(row)
            #row.append(doc.date.isoformat(), 
    except Exception as e:
        raise
        return "Error: %s" % e.message, 400, {'Content-Type':'text/plain'}
    buf = StringIO()
    csvwriter = csv.writer(buf)
    for row in results:
        csvwriter.writerow(row)
    buf.seek(0)
    buf = buf.read()
    return buf, 200, {'Content-Type':'text/csv'}
