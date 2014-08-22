from datetime import datetime, timedelta
from collections import defaultdict, Counter

from flask import render_template, make_response, redirect, jsonify, url_for
from ioos_catalog import app, db, prettydate
from ioos_catalog.tasks.reindex_services import region_map
from ioos_catalog.views.ra import provider_info as p_info

# @TODO: really belongs in app __init__ but need to move region_map
@app.context_processor
def inject_ra_providers():
        ra_list, national_list = [], []
        for key in p_info:
            if p_info[key].get('provider_type') == 'national':
                national_list.append(key)
            #assume unset provider types are regional by default
            elif p_info[key].get('provider_type', 'regional') == 'regional':
                ra_list.append(key)
        return {'ra_providers': sorted(ra_list),
                'national_partners': sorted(national_list)}

@app.route('/', methods=['GET'])
def index():
    # provider list
    providers = sorted(region_map.keys())

    # service counts by provider
    counts_by_provider = db.Service.count_types_by_provider_flat()
    dataset_counts_by_provider = db.Dataset.count_types_by_provider_flat()

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

