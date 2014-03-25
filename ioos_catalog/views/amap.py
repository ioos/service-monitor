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

@app.route('/map/')
def asset_map():

    g.title = "Asset Map"

    # TEST
    # grab AOOS datasets
    datasets = list(db.Dataset.find({'services.data_provider':'AOOS'}))

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

        pa = shapely.geometry.asShape(geometry)
        geometry = shapely.geometry.geo.mapping(pa.simplify(1))

        gj = {'type':'Feature',
              'properties':{'asset_type':s.get('asset_type'),
                            'data_provider':s.get('data_provider'),
                            'name': s.get('name')},
              'geometry':geometry}

        return gj

    geojsons = [make_geojson(s) for s in chain.from_iterable((d.services for d in datasets))]
    geojsons = filter(lambda x: x is not None, geojsons)

    #geojsons = [v.services[0].get('geojson') for v in assets['BUOY']][:] + [v.services[0].get('geojson') for v in assets['CGRID']][0:5]

    geojsons = geojsons[0:25]
    #points_geojsons = [gj for gj in geojsons if gj['geometry']['type'] == 'Point']
    #coords = []
    #map(coords.append, (gj['geometry']['coordinates'] for gj in points_geojsons))

    #return jsonify({'type':'FeatureCollection', 'features':geojsons})
    #return jsonify({'type':'FeatureCollection', 'features':[{'type':'Feature', 'properties':{'hoo':'stank'}, 'geometry':{'coordinates':coords, 'type':'MultiPoint'}}]})

    return render_template('asset_map.html', geojsons=geojsons)

