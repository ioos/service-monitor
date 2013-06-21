from flask import render_template, redirect, url_for, request, flash, jsonify
from ioos_service_monitor import app, db
import json
#from ioos_service_monitor.models import remove_mongo_keys
#from ioos_service_monitor.views.helpers import requires_auth
#from ioos_service_monitor.tasks.dataset import calc
#from rq import cancel_job
from flask.ext.wtf import Form
from wtforms import TextField, IntegerField

class ServiceForm(Form):
    name               = TextField(u'Name')
    url                = TextField(u'URL')
    service_id         = TextField(u'Service ID')
    service_type       = TextField(u'Service Type')
    data_provider      = TextField(u'Data Provider')
    geophysical_params = TextField(u'Geophysical Parameters')
    contact            = TextField(u'Contact Emails', description="A list of emails separated by commas")
    interval           = IntegerField(u'Update Interval', description="In MS")

@app.route('/services/', methods=['GET'])
def services():
    f = ServiceForm()
    services = db.Service.find()
    return render_template('services.html', services=services, form=f)

@app.route('/services/<ObjectId:service_id>', methods=['GET'])
def show_service(service_id):
    service = db.Service.find_one({'_id':service_id})
    return render_template('show_service.html', service=service)

@app.route('/services/', methods=['POST'])
def add_service():
    f = ServiceForm()
    service = db.Service()
    #if f.validate():
    f.populate_obj(service)
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

