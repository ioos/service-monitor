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

@app.route('/map/', defaults={'filter_provider':None}, methods=['GET'])
@app.route('/map/<path:filter_provider>/', methods=['GET'])
def asset_map(filter_provider):

    g.title = "Asset Map"

    regions = sorted(region_map.iterkeys())

    filters = {}
    titleparts = []

    if filter_provider is not None and filter_provider != "null":
        titleparts.append(filter_provider)
        filters['services.data_provider'] = filter_provider

    else:
        filters['services.data_provider'] = 'NERACOOS'        # smaller

    datasets = list(db.Dataset.find(filters))

    # bucket them by asset type
    #assets = defaultdict(list)

    #for d in datasets:
    #    assets[d.services[0].get('asset_type')].append(d)

    # 5 of each please
    #for k, v in assets.iteritems():
    #    v = v[0:5]

    def make_geojson(s):
        geometry = s.get('geojson')

        if geometry is None:
            return None

        if len(geometry['coordinates']) > 1000:
            return None

        def flatten(L):
            for item in L:
                try:
                    for i in flatten(item):
                        yield i
                except TypeError:
                    yield item

        f = next(flatten(geometry['coordinates']))
        if f > 180:
            return None

        pa = shapely.geometry.asShape(geometry)
        geometry = shapely.geometry.geo.mapping(pa.simplify(1))

        gj = {'type':'Feature',
              'properties':{'asset_type':s.get('asset_type'),
                            'sid':str(s.get('service_id')),
                            'data_provider':s.get('data_provider'),
                            'name': s.get('name')},
              'geometry':geometry}

        return gj

    geojsons = [make_geojson(s) for s in chain.from_iterable((d.services for d in datasets))]
    geojsons = filter(lambda x: x is not None, geojsons)

    #geojsons = [v.services[0].get('geojson') for v in assets['BUOY']][:] + [v.services[0].get('geojson') for v in assets['CGRID']][0:5]

    #geojsons = geojsons[0:500]
    #points_geojsons = [gj for gj in geojsons if gj['geometry']['type'] == 'Point']
    #coords = []
    #map(coords.append, (gj['geometry']['coordinates'] for gj in points_geojsons))

    #return jsonify({'type':'FeatureCollection', 'features':geojsons})
    #return jsonify({'type':'FeatureCollection', 'features':[{'type':'Feature', 'properties':{'hoo':'stank'}, 'geometry':{'coordinates':coords, 'type':'MultiPoint'}}]})

    return render_template('asset_map.html', regions=regions,
                                             filters=filters,
                                             geojsons=geojsons)


@app.route('/map/geojson/<path:filter_provider>/', methods=['GET'])
def geoj(filter_provider):
    datasets = list(db.Dataset.find({'services.data_provider':filter_provider}))

    features = []

    grouped = defaultdict(list)
    nongrouped = []

    for d in datasets:
        if not d.uid.startswith('urn'):
            nongrouped.append((d._id, d.services[0]['geojson'], d.services[0]['name'], d.services[0]['asset_type']))
            continue

        splits = d.uid.split(':')
        grouped[splits[3]].append(d)

    # grouped
    for g, vals in grouped.iteritems():

        coords = []
        map(coords.append, (v.services[0]['geojson']['coordinates'] for v in vals))

        feat = {'type':'Feature',
                'properties':{'group':g,
                              'name':g,
                              'id':grouped.keys().index(g)},
                'geometry': {
                    'type':'MultiPoint',
                    'coordinates':coords,
                }}

        features.append(feat)

    # nongrouped
    for g in nongrouped:
        if g[1] is None:
            continue

        feat = {'type':'Feature',
                'properties':{'id':str(g[0]),
                              'name':g[2]},
                'geometry': g[1]}
        features.append(feat)

    doc = {'type':'FeatureCollection',
           'features':features}

    return jsonify(doc)

