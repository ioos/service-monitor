from datetime import datetime
from collections import defaultdict

from flask import render_template, make_response, redirect, jsonify
from ioos_catalog import app, db

@app.route('/', methods=['GET'])
def index():
    counts       = db.Service.count_types()
    stats        = list(db.PingLatest.find().sort([('updated',-1)]).limit(8))
    services     = db.Service.find({'_id':{'$in':[p.service_id for p in stats]}})
    services     = {s._id:s for s in services}

    # temp
    providers = sorted(db['services'].distinct('data_provider'))

    # service counts by provider
    counts_by_provider = db.Service.count_types_by_provider()
    dataset_counts_by_provider = db.Dataset.count_types_by_provider()

    # asset counts (not by provider)
    asset_counts = defaultdict(int)
    for v in dataset_counts_by_provider.itervalues():
        for atn, atc in v.iteritems():
            if not atn:
                atn = 'null'
            asset_counts[atn] += atc

    return render_template('index.html',
                           counts=counts,
                           asset_counts=dict(asset_counts),
                           counts_by_provider=counts_by_provider,
                           dataset_counts_by_provider=dataset_counts_by_provider,
                           stats=stats,
                           services=services,
                           providers=providers)

@app.route('/crossdomain.xml', methods=['GET'])
def crossdomain():
    domain = """
    <cross-domain-policy>
        <allow-access-from domain="*"/>
        <site-control permitted-cross-domain-policies="all"/>
        <allow-http-request-headers-from domain="*" headers="*"/>
    </cross-domain-policy>
    """
    response = make_response(domain)
    response.headers["Content-type"] = "text/xml"
    return response

