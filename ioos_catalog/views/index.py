from datetime import datetime
from collections import defaultdict

from flask import render_template, make_response, redirect, jsonify
from ioos_catalog import app, scheduler, db

from ioos_catalog.tasks.regulator import regulate

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

def serialize_date(date):
    if date is not None:
        return date.isoformat()

def serialize_job(job,dt):
    return dict(
        id=job.id,
        scheduled_at=serialize_date(dt),
        created_at=serialize_date(job.created_at),
        enqueued_at=serialize_date(job.enqueued_at),
        ended_at=serialize_date(job.ended_at),
        origin=job.origin,
        result=str(job._result),
        exc_info=job.exc_info,
        description=job.description,
        args=job.args,
        meta=job.meta)

@app.route('/jobs/clear', methods=['GET'])
def clear_jobs():
    for job in scheduler.get_jobs():
        scheduler.cancel(job)
    return jsonify({ "status" : "ok" })

@app.route('/jobs', methods=['GET'])
def jobs():
    jobs = []
    for job,dt in scheduler.get_jobs(with_times=True):
        jobs.append(serialize_job(job,dt))
    return jsonify({ "jobs" : jobs })

@app.route('/regulate', methods=['GET'])
def reg():

    existed = False

    jobs = scheduler.get_jobs()
    for j in jobs:
        if j.func == regulate:
            existed = True
            scheduler.cancel(j)
            break

    scheduler.schedule(
        scheduled_time=datetime.utcnow(), # Time for first execution
        func=regulate,                    # Function to be queued
        interval=3600,                    # Time before the function is called again, in seconds
        repeat=None,                      # Repeat this number of times (None means repeat forever)
        result_ttl=3600*2                 # How long to keep the results
    )

    if existed:
        msg = "re-scheduled"
    else:
        msg = "regulated"

    return jsonify({"message" : msg})

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

