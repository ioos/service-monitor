from datetime import datetime, timedelta
from collections import defaultdict, Counter

from flask import render_template, make_response, redirect, jsonify, url_for
from ioos_catalog import app, db, prettydate

@app.route('/', methods=['GET'])
def index():
    counts       = db.Service.count_types()

    # temp
    providers = [u'All'] + sorted(db['services'].distinct('data_provider'))

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

    # service sum for "all RAs"
    c = Counter()
    for scounts in counts_by_provider.itervalues():
        c.update(scounts)

    counts_by_provider[u'All'] = dict(c.items())

    # dataset sum for an "all RAs"
    c = Counter()
    for dscounts in dataset_counts_by_provider.itervalues():
        c.update(dscounts)

    dataset_counts_by_provider[u'All'] = dict(c.items())

    # get list of most recent updates since yesterday
    since        = datetime.utcnow() - timedelta(hours=24)

    stats        = list(db.PingLatest.find({'updated':{'$gte':since}}).sort([('updated',-1)]))
    upd_datasets = list(db.Dataset.find({'updated':{'$gte':since}}).sort([('updated', -1)]))
    services     = db.Service.find({'_id':{'$in':[p.service_id for p in stats]}})
    services     = {s._id:s for s in services}

    updates = []

    for s in stats:
        updates.append({'data_provider':services[s._id].data_provider,
                        'name': services[s._id].name,
                        'service_type': services[s._id].service_type,
                        'update_type': 'ping',
                        'updated': int(s.updated.strftime('%s')),
                        'updated_display': prettydate(s.updated),
                        'data': {'code':s.last_response_code,
                                 'time':s.last_response_time},
                        '_id': str(s._id),
                        'url': url_for('show_service', service_id=s._id)})

    for d in upd_datasets:
        for s in d.services:
            # due to the grouping, we may have older ones in this dataset
            if s['updated'] != d.updated:
                continue

            updates.append({'data_provider':s['data_provider'],
                            'name':s['name'],
                            'service_type': s['service_type'],
                            'update_type':'harvest',
                            'updated': int(d.updated.strftime('%s')),
                            'updated_display': prettydate(d.updated),
                            'data':{},
                            'id':str(d._id),
                            'url':url_for('show_dataset', dataset_id=d._id)})

    return render_template('index.html',
                           counts=counts,
                           asset_counts=dict(asset_counts),
                           counts_by_provider=counts_by_provider,
                           dataset_counts_by_provider=dataset_counts_by_provider,
                           updates=updates,
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

