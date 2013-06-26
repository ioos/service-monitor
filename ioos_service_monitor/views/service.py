from flask import render_template, redirect, url_for, request, flash, jsonify
from ioos_service_monitor import app, db, scheduler
import json
import urlparse
from datetime import datetime, timedelta
#from ioos_service_monitor.models import remove_mongo_keys
#from ioos_service_monitor.views.helpers import requires_auth
from ioos_service_monitor.tasks.stat import ping_service_task
from flask.ext.wtf import Form
from wtforms import TextField, IntegerField, SelectField
from ioos_service_monitor.models.stat import Stat
from pymongo import DESCENDING

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

@app.route('/services/', defaults={'filter_provider':None, 'filter_type':None}, methods=['GET'])
@app.route('/services/filter/<filter_provider>/<filter_type>', methods=['GET'])
def services(filter_provider, filter_type):
    filters = {}

    if filter_provider is not None and filter_provider != "null":
        filters['data_provider'] = filter_provider

    if filter_type is not None and filter_type != "null":
        filters['service_type'] = filter_type

    f                 = ServiceForm()
    services          = list(db.Service.find(filters))
    latest_stats      = db.Stat.latest_stats_by_service(1)
    last_weekly_stats = db.Stat.latest_stats_by_service_by_time(time_delta=timedelta(days=7))

    for s in services:
        if s._id in latest_stats:
            s.last_operational_status = latest_stats[s._id]['operational_status']
            s.last_response_time      = latest_stats[s._id]['response_time']
            s.last_update             = latest_stats[s._id]['created']
        else:
            s.last_operational_status = 0
            s.last_response_time      = None
            s.last_update             = None

        if s._id in last_weekly_stats:
            s.avg_operational_status  = last_weekly_stats[s._id]['operational_status']
            s.avg_response_time       = last_weekly_stats[s._id]['response_time']
        else:
            s.avg_operational_status  = 0
            s.avg_response_time       = None

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
    providers = db.Service.raw_collection().distinct('data_provider')

    return render_template('services.html', services=services, form=f, tld_stats=tld_stats, providers=providers, filters=filters)

@app.template_filter('status_icon')
def status_icon_helper(status_val):
    if status_val:
        return "<i class=\"icon-ok\"></i>"
    return "<i class=\"icon-exclamation-sign\"></i>"

@app.route('/services/<ObjectId:service_id>', methods=['GET'])
def show_service(service_id):
    service = db.Service.find_one({'_id':service_id})
    stats = db.Stat.find({'service_id':service_id}).sort('created', DESCENDING).limit(15)

    avg_response_time = service.response_time(15)

    return render_template('show_service.html', service=service, stats=stats, avg_response_time=avg_response_time)

@app.route('/services/', methods=['POST'])
def add_service():
    f = ServiceForm()
    service = db.Service()
    #if f.validate():
    f.populate_obj(service)
    url = urlparse.urlparse(service.url)
    service.tld = url.hostname
    service.save()

    flash("Service '%s' Registered" % service.name, 'success')
    return redirect(url_for('services'))
    #job = service_queue.enqueue_call(func=calc, args=(unicode(service['_id']),))
    #service.task_id = unicode(job.id)
    #service.save()

@app.route('/services/<ObjectId:service_id>', methods=['POST'])
def edit_service_submit(service_id):
    f = ServiceForm()
    service = db.Service.find_one({'_id':service_id})

    #@TODO: validation
    f.populate_obj(service)

    url = urlparse.urlparse(service.url)
    service.tld = url.hostname
    service.save()

    #@TODO: scheduled task redo

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
    st = Stat()
    st.service_id = service_id

    return st.ping_service()

@app.route('/services/<ObjectId:service_id>/start_monitoring', methods=['GET'])
def start_monitoring_service(service_id):
    s = db.Service.find_one({'_id':service_id})
    assert s is not None

    scheduler.schedule(scheduled_time=datetime.now(),
                       func=ping_service_task,
                       args=(unicode(service_id),),
                       interval=s.interval,
                       repeat=None,
                       result_ttl=s.interval * 2)

    flash("Scheduled monitoring for '%s' service" % s.name)
    return redirect(url_for('services'))

@app.route('/services/<ObjectId:service_id>/edit', methods=['GET'])
def edit_service(service_id):
    service = db.Service.find_one({'_id':service_id})
    f = ServiceForm(obj=service)
    return render_template('edit_service.html', service=service, form=f)

