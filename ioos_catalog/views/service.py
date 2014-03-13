import json
import urlparse
from datetime import datetime, timedelta
from pymongo import DESCENDING
from flask.ext.wtf import Form
from flask import render_template, redirect, url_for, request, flash, jsonify, Response
from wtforms import TextField, IntegerField, SelectField
from bson import json_util

from ioos_catalog import app, db, scheduler, support_jsonp
from ioos_catalog.models.stat import Stat
from ioos_catalog.tasks.stat import ping_service_task
from ioos_catalog.tasks.reindex_services import reindex_services
from ioos_catalog.tasks.harvest import harvest

class ServiceForm(Form):
    name               = TextField(u'Name')
    url                = TextField(u'URL')
    service_id         = TextField(u'Service ID')
    service_type       = SelectField(u'Service Type', choices=[(u'WMS', u'WMS'),
                                                               (u'DAP', u'DAP'),
                                                               (u'WCS', u'WCS'),
                                                               (u'SOS', u'SOS')])
    data_provider      = TextField(u'Data Provider')
    geophysical_params = TextField(u'Geophysical Parameters')
    contact            = TextField(u'Contact Emails', description="A list of emails separated by commas")
    interval           = IntegerField(u'Update Interval', description="In seconds")

@app.route('/services/', defaults={'filter_provider':None, 'filter_type':None, 'oformat':None}, methods=['GET'])
@app.route('/services/filter/<path:filter_provider>', defaults={'filter_type':None, 'oformat':None}, methods=['GET'])
@app.route('/services/filter/<path:filter_provider>/<filter_type>', defaults={'oformat':None}, methods=['GET'])
@app.route('/services/filter/<path:filter_provider>/<filter_type>/<oformat>', methods=['GET'])
@support_jsonp
def services(filter_provider, filter_type, oformat):
    filters = {}

    if filter_provider is not None and filter_provider != "null":
        filters['data_provider'] = filter_provider

    if filter_type is not None and filter_type != "null":
        filters['service_type'] = filter_type

    f                 = ServiceForm()
    services          = list(db.Service.find(filters))
    sids              = [s._id for s in services]
    latest_stats      = db.Stat.latest_stats_by_service(service_ids=sids)
    last_weekly_stats = db.Stat.latest_stats_by_service_by_time(time_delta=timedelta(days=7), service_ids=sids)

    for s in services:
        if s._id in latest_stats:
            s.last_operational_status = latest_stats[s._id]['operational_status']
            s.last_response_time      = latest_stats[s._id]['response_time']
            s.last_response_code      = latest_stats[s._id]['response_code']
            s.last_update             = latest_stats[s._id]['created']
        else:
            s.last_operational_status = 0
            s.last_response_time      = None
            s.last_response_code      = None
            s.last_update             = None

        if s._id in last_weekly_stats:
            s.avg_operational_status  = last_weekly_stats[s._id]['operational_status']
            s.avg_response_time       = last_weekly_stats[s._id]['response_time']
        else:
            s.avg_operational_status  = 0
            s.avg_response_time       = None

    if oformat is not None and oformat == 'json':
        resp = json.dumps({'services':services}, default=json_util.default)
        return Response(resp, mimetype='application/json')

    # get TLD grouped statistics
    tld_stats = {}
    filter_ids = None
    if len(filters):
        filter_ids = [s._id for s in services]

    tld_groups = db.Service.group_by_tld(filter_ids)
    for k, v in tld_groups.iteritems():
        tld_stats[k] = {'ok':0, 'total':0}
        for sid in v:
            tld_stats[k]['total'] += 1
            if sid in latest_stats and int(latest_stats[sid]['operational_status']) == 1:
                tld_stats[k]['ok'] += 1

    # get list of unique providers in system
    providers = db["services"].distinct('data_provider')

    return render_template('services.html', services=services, form=f, tld_stats=tld_stats, providers=providers, filters=filters)

@app.template_filter('status_icon')
def status_icon_helper(status_val):
    if status_val:
        return "<span class=\"glyphicon glyphicon-ok\"></span>"
    return "<span class=\"glyphicon glyphicon-exclamation-sign\"></span>"

@app.route('/services/<ObjectId:service_id>', methods=['GET'])
def show_service(service_id):
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)

    service = db.Service.find_one({'_id':service_id})

    stats = list(db.Stat.find({'service_id':service_id,
                          'created':{'$lte':now,
                                     '$gte':week_ago}}).sort('created', DESCENDING))

    avg_response_time = sum([x.response_time for x in stats if x.response_time]) / len(stats) if len(stats) else 0

    ping_data = {'good':[], 'bad':[]}
    for i, x in enumerate(reversed(stats)):
        v = {'x':i, 'y':x.response_time or 250}
        if x.operational_status:
            ping_data['good'].append(v)
            ping_data['bad'].append({'x':i,'y':0})
        else:
            ping_data['bad'].append(v)
            ping_data['good'].append({'x':i,'y':0})

    # Organize datasets by type.  Include the UID and _id of each dataset in the output so we can link to them.
    datasets = db.Dataset.aggregate([
        {'$match'   : { 'services.service_id' : service_id }},
        {'$group'   : { '_id'       : '$services.asset_type',
                        'datasets'  : { '$push' : { 'uid' : '$uid', '_id' : '$_id' } } } }

    ])

    harvests = { 'next' : None, 'last' : None }
    pings    = { 'next' : None, 'last' : None }
    for job in scheduler.get_jobs(with_times=True):
        if job[0].id == service.harvest_job_id:
            harvests['last'] = job[0].ended_at
            harvests['next'] = job[1]
        elif job[0].id == service.ping_job_id:
            if len(stats) > 0:
                pings['last'] = stats[0].created
            pings['next'] = job[1]

    # get cc/metamap
    metadata_parent = db.Metadata.find_one({'ref_id':service._id})
    metadatas = {}
    if metadata_parent:
        metadatas = {m['checker']:m for m in metadata_parent.metadata if m['service_id'] == service._id}

    return render_template('show_service.html', service=service, stats=stats, avg_response_time=avg_response_time, ping_data=ping_data, datasets=datasets, harvests=harvests, pings=pings, metadatas=metadatas)

@app.route('/services/', methods=['POST'])
def add_service():
    f = ServiceForm()
    service = db.Service()
    #if f.validate():
    f.populate_obj(service)
    url = urlparse.urlparse(service.url)
    service.tld = url.hostname
    service.save()

    service.schedule_ping()

    flash("Service '%s' Registered" % service.name, 'success')
    return redirect(url_for('services'))

@app.route('/services/<ObjectId:service_id>', methods=['POST'])
def edit_service_submit(service_id):
    f = ServiceForm()
    service = db.Service.find_one({'_id':service_id})

    #@TODO: validation
    f.populate_obj(service)

    url = urlparse.urlparse(service.url)
    service.tld = url.hostname
    service.save()

    service.schedule_ping()

    flash("Service '%s' updated" % service.name, 'success')
    return redirect(url_for('show_service', service_id=service_id))

@app.route('/services/<ObjectId:service_id>/delete', methods=['POST'])
def delete_service(service_id):
    service = db.Service.find_one( { '_id' : service_id } )
    service.delete()

    flash("Deleted service %s" % service.name)
    return redirect(url_for('services'))

@app.route('/services/<ObjectId:service_id>/ping', methods=['GET'])
def ping_service(service_id):
    st = db.Stat()
    st.service_id = service_id

    ret = st.ping_service()

    st.save()
    flash("Ping returned: %s" % ret)
    return redirect(url_for('show_service', service_id=service_id))

@app.route('/services/<ObjectId:service_id>/harvest', methods=['GET'])
def harvest_service(service_id):
    s = db.Service.find_one({ '_id' : service_id })

    h = harvest(service_id)
    flash(h)
    return redirect(url_for('show_service', service_id=service_id))

@app.route('/services/<ObjectId:service_id>/start_monitoring', methods=['POST'])
def start_monitoring_service(service_id):
    s = db.Service.find_one({'_id':service_id})
    assert s is not None

    s.schedule_ping()

    flash("Started monitoring the '%s' service" % s.name)
    return redirect(url_for('show_service', service_id=service_id))

@app.route('/services/<ObjectId:service_id>/stop_monitoring', methods=['POST'])
def stop_monitoring_service(service_id):
    s = db.Service.find_one({'_id':service_id})
    assert s is not None

    s.cancel_ping()

    flash("Stopped monitoring the '%s' service" % s.name)
    return redirect(url_for('show_service', service_id=service_id))

@app.route('/services/<ObjectId:service_id>/start_harvesting', methods=['POST'])
def start_harvesting_service(service_id):
    s = db.Service.find_one({'_id':service_id})
    assert s is not None

    s.schedule_harvest()

    flash("Started harvesting the '%s' service" % s.name)
    return redirect(url_for('show_service', service_id=service_id))

@app.route('/services/<ObjectId:service_id>/stop_harvesting', methods=['POST'])
def stop_harvesting_service(service_id):
    s = db.Service.find_one({'_id':service_id})
    assert s is not None

    s.cancel_harvest()

    flash("Stopped harvesting the '%s' service" % s.name)
    return redirect(url_for('show_service', service_id=service_id))

@app.route('/services/<ObjectId:service_id>/edit', methods=['GET'])
def edit_service(service_id):
    service = db.Service.find_one({'_id':service_id})
    f = ServiceForm(obj=service)
    return render_template('edit_service.html', service=service, form=f)

@app.route('/services/reindex', methods=['GET'])
def reindex():
    jobs = scheduler.get_jobs()

    for job in jobs:
        if job.func == reindex_services or job.description == "ioos_catalog.views.services.reindex()":
           scheduler.cancel(job)

    scheduler.schedule(
        scheduled_time=datetime.utcnow(), # Time for first execution
        func=reindex_services,            # Function to be queued
        interval=21600,                   # Time before the function is called again, in seconds
        repeat=None,                      # Repeat this number of times (None means repeat forever)
        result_ttl=40000,                 # How long to keep the results
        timeout=1200                      # Default timeout of 180 seconds may not be enough
    )

    return jsonify({"message" : "scheduled"})

@app.route('/services/feed.xml', methods=['GET'])
def atom_feed():
    services = list(db.Service.find({'service_type': {'$ne':'DAP'}}))

    for s in services:
        # Make the default TO the default for the FGDC feed... always.
        #if s.contact is None or s.contact != "":
        s.contact = app.config.get("MAIL_DEFAULT_TO")

    return Response(render_template('feed.xml', services=services), mimetype='text/xml')

@app.route('/services/devfeed.xml', methods=['GET'])
def dev_atom_feed():
    services = list(db.Service.find())

    for s in services:
        #if s.contact is None or s.contact != "":
        s.contact = app.config.get("MAIL_DEFAULT_TO")

    return Response(render_template('feed.xml', services=services), mimetype='text/xml')

@app.route('/services/schedule_all', methods=['GET'])
def schedule_all():
    services = db.Service.find({'ping_job_id':None})
    map(lambda x: x.schedule_ping(), services)

    flash("Scheduled %d pings" % services.count())
    return redirect(url_for('services'))

@app.route('/services/stop_all', methods=['GET'])
def stop_all():
    services = db.Service.find({'ping_job_id': {'$ne':None}})
    map(lambda x: x.cancel_ping(), services)

    flash("Stopped %d pings" % services.count())
    return redirect(url_for('services'))

@app.route('/services/daily', methods=['GET'], defaults={'year':None, 'month':None, 'day':None})
@app.route('/services/daily/<int:year>/<int:month>/<int:day>', methods=['GET'])
def daily(year, month, day):
    end_time = None
    if year is not None and month is not None and day is not None:
        end_time = datetime.strptime("%s/%s/%s" % (year, month, day), "%Y/%m/%d")

    failed_services, services, end_time, start_time = db.Service.get_failures_in_time_range(end_time=end_time)
    return render_template("daily_service_report_page.html", services=services, failed_services=failed_services, start_time=start_time, end_time=end_time)

