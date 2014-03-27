import json
import urlparse
from datetime import datetime, timedelta
from pymongo import DESCENDING
from flask.ext.wtf import Form
from flask import render_template, redirect, url_for, request, flash, jsonify, Response, g
from wtforms import TextField, IntegerField, SelectField
from bson import json_util
from collections import defaultdict
from itertools import chain
import shapely.geometry

from ioos_catalog import app, db, scheduler, support_jsonp, requires_auth
from ioos_catalog.tasks.reindex_services import region_map

@app.route('/map/', methods=['GET'])
def asset_map():

    g.title = "Asset Map"
    regions = sorted(region_map.iterkeys())

    return render_template('asset_map.html', regions=regions)


@app.route('/map/geojson/<path:filter_provider>/', methods=['GET'])
def geoj(filter_provider):
    datasets = list(db.Dataset.find({'services.data_provider':filter_provider}))

    features = []

    grouped = defaultdict(list)
    nongrouped = []

    for d in datasets:
        if not d.uid.startswith('urn'):
            for s in d.services:
                if s.get('geojson', None) is None:
                    continue

                feat = {'type':'Feature',
                        'properties':{'id':str(d._id),
                                      'name':s['name']},
                        'geometry': s.get('geojson')}

                features.append(feat)

            continue

        splits = d.uid.split(':')
        grouped[":".join(splits[0:4])].append(d)

    # grouped
    for g, vals in grouped.iteritems():

        coords = []

        for v in vals:
            for s in v.services:
                if s.get('geojson', None) is None:
                    continue

                coords.append(s.get('geojson')['coordinates'])

        feat = {'type':'Feature',
                'properties':{'group':g,
                              'name':g,
                              'id':grouped.keys().index(g)},
                'geometry': {
                    'type':'MultiPoint',
                    'coordinates':coords,
                }}

        features.append(feat)

    doc = {'type':'FeatureCollection',
           'features':features}

    return jsonify(doc)

