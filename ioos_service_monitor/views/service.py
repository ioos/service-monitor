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

@app.route('/services/', methods=['GET'])
def services():
    f = ServiceForm()
    services = db.Service.find()
    return render_template('services.html', services=services, form=f)

@app.route('/services/<ObjectId:service_id>', methods=['GET'])
def show_service(service_id):
    service = db.Service.find_one({'_id':service_id})
    stats = db.Stat.find({'service_id':service_id})
    raw_db = db.connection[app.config.get('MONGODB_DATABASE')][db.Stat.__collection__]
    agg_stats_query = [{"$match":{"service_id":service_id}},
                       {"$group":{"_id":None, "avg":{"$avg":"$response_time"}}}]
    avg_response_time = round(raw_db.aggregate(agg_stats_query)['result'][0]['avg'], 2)

    #asq_3mo = agg_stats_query[:]
    #asq_3mo[0]['$match'].update({"created": {"$gte": datetime.utcnow() - timedelta(days=92)}})
    #avg_3mo = round(raw_db.aggregate(asq_3mo)['result'][0]['avg'])

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
