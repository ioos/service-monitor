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

from ioos_catalog import app, db, support_jsonp, requires_auth
from ioos_catalog.tasks.reindex_services import region_map

@app.route('/map/', defaults={'filter_provider': 'SECOORA'}, methods=['GET'])
@app.route('/map/<path:filter_provider>', methods=['GET'])
def asset_map(filter_provider):
    # filter_provider ultimately is do-nothing arg that serves as a placeholder
    # for the location to be processed by javascript

    g.title = "Asset Map"
    regions = sorted(region_map.iterkeys())

    return render_template('asset_map.html', regions=regions)


@app.route('/map/geojson/<path:filter_provider>/', methods=['GET'])
def geoj(filter_provider):

    query_params = {}
    if filter_provider != 'null':
        query_params['services.data_provider'] = filter_provider

    datasets = list(db.Dataset.find(query_params))

    features = []

    grouped = defaultdict(list)
    nongrouped = []

    for d in datasets:
        if not d.uid.startswith('urn'):
            for idx, s in enumerate(d.services):
                if s.get('geojson', None) is None:
                    continue

                feat = {'type':'Feature',
                        'properties':{'id':str(d._id),
                                      'sindex': idx,        # service index
                                      'name':s['name'],
                                      'description':s['description']},
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

@app.route('/map/details/<ObjectId:dataset_id>/<int:sindex>', methods=['GET'])
def details(dataset_id, sindex):
    dataset = db.Dataset.find_one({'_id':dataset_id})
    s = dataset.services[sindex]

    # get details from service
    service = db.Service.find_one({'_id':s['service_id']})
    pl      = db.PingLatest.find_one({'service_id':s['service_id']})

    retval = {'name':s.get('name', 'UNKNOWN'),
              'description':s.get('description', ''),
              'data_provider':s.get('data_provider', ''),
              'asset_type': s.get('asset_type', 'UNKNOWN'),
              'updated':str(s['updated']),
              'uid':dataset.uid,
              'variables':s.get('variables', []),
              'keywords':s.get('keywords', []),
              'dataset_link':url_for('show_dataset', dataset_id=dataset_id),
              'service_link':url_for('show_service', service_id=s['service_id']),
              'service_name':service.name,
              'service_type':service.service_type,
              'service_recent_uptime':'',
              'cc_score':''}

    # if there exists ping data, show it
    if pl:
              retval['service_last_ping_time'] = str(pl.updated)
              retval['service_last_status'] = pl.last_operational_status
    # otherwise just leave it blank instead of failing entirely
    else:
              retval['service_last_ping_time'] = 'Never'
              retval['service_last_status'] = 'N/A'

    return jsonify(retval)
