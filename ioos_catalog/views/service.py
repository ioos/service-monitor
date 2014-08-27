import json
import urlparse
from datetime import datetime, timedelta
from pymongo import DESCENDING
from flask.ext.wtf import Form
from flask import render_template, redirect, url_for, request, flash, jsonify, Response, g
from wtforms import TextField, IntegerField, SelectField
from bson import json_util

from ioos_catalog import app, db, queue, support_jsonp, requires_auth
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
@app.route('/services/filter/', defaults={'filter_provider':None, 'filter_type':None, 'oformat':None}, methods=['GET'])
@app.route('/services/filter/<path:filter_provider>', defaults={'filter_type':None, 'oformat':None}, methods=['GET'])
@app.route('/services/filter/<path:filter_provider>/<filter_type>', defaults={'oformat':None}, methods=['GET'])
@app.route('/services/filter/<path:filter_provider>/<filter_type>/<oformat>', methods=['GET'])
@support_jsonp
def services(filter_provider, filter_type, oformat):
    provider_mapping = {
        "NOS-CO-OPS" : "NOS/CO-OPS", # The slash disriupts proper routing
        "USGS-CMGP"  : "USGS/CMGP"
    }
    if filter_provider in provider_mapping:
        filter_provider = provider_mapping[filter_provider]

    # it's hard to get flask to route correctly with paths/json - fixup for "/" providers with no oformat
    if oformat == "null":
        filter_provider = "/".join([filter_provider, filter_type])
        filter_type = "null"
        oformat = None

    filters = {'active':True}
    titleparts = []

    if filter_provider is not None and filter_provider != "null":
        titleparts.append(filter_provider)
        filters['data_provider'] = {'$in': filter_provider.split(',')}

    if filter_type is not None and filter_type != "null":
        titleparts.append(filter_type)
        filters['service_type'] = {'$in': filter_type.split(',')}

    # build title
    titleparts.append("Services")
    g.title = " ".join(titleparts)

    f                 = ServiceForm()
    services          = list(db.Service.find(filters))
    sids              = [s._id for s in services]
    latest_stats      = db.PingLatest.find({'service_id':{'$in':sids}})#, {'service_id':1,
                                                                       #  'last_operational_status':1,
                                                                       #  'last_response_time':1,
                                                                       #  'last_response_code':1,
                                                                       #  'updated':1})
    # map them down
    latest_stats      = {p.service_id:p for p in latest_stats}
    service_stats     = {} # mapping of service ids to summary stats about that service, or blanked versions

    for s in services:
        service_stats[s._id] = {'last_operational_status' : 0,
                                'last_response_time'      : None,
                                'last_response_code'      : None,
                                'last_update'             : None,
                                'avg_response_time'       : None}

        if s._id in latest_stats:
            stat = latest_stats[s._id]

            service_stats[s._id]['last_operational_status'] = stat.last_operational_status
            service_stats[s._id]['last_response_time']      = stat.last_response_time
            service_stats[s._id]['last_response_code']      = stat.last_response_code
            service_stats[s._id]['last_update']             = stat.updated

            # calc averages
            #good_statuses = [x for x in stat.operational_statuses if x is not None]
            good_responses = [x for x in stat.response_times if x is not None]

            if len(good_responses):
                total = len(stat.response_times)

                #service_stats[s._id]['avg_operational_status  = float(good_statuses.count(True)) / total
                service_stats[s._id]['avg_response_time']       = float(sum(good_responses)) / total
            else:
                #service_stats[s._id]['avg_operational_status  = 0
                service_stats[s._id]['avg_response_time']       = None

    if oformat is not None and oformat == 'json':
        resp = json.dumps({'services':[dict(dict(s).items() + service_stats[s._id].items()) for s in services]}, default=json_util.default)
        return Response(resp, mimetype='application/json')

    # get TLD grouped statistics
    tld_stats = {}

    tld_groups = db.Service.group_by_tld(sids)
    for k, v in tld_groups.iteritems():
        tld_stats[k] = {'ok':0, 'total':0}
        for sid in v:
            tld_stats[k]['total'] += 1
            if sid in latest_stats and latest_stats[sid].last_operational_status:
                tld_stats[k]['ok'] += 1

    # get list of unique providers in system
    providers = db["services"].distinct('data_provider')

    return render_template('services.html', services=services, service_stats=service_stats, form=f, tld_stats=tld_stats, providers=providers, filters=filters)

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

    g.title = service.name

    # Organize datasets by type.  Include the UID and _id of each dataset in the output so we can link to them.
    datasets = db.Dataset.aggregate([
        {'$match'   : { 'services.service_id' : service_id }},
        {'$group'   : { '_id'       : '$services.asset_type',
                        'datasets'  : { '$push' : { 'uid' : '$uid', '_id' : '$_id' } } } }
    ])

    # get cc/metamap
    metadata_parent = db.Metadata.find_one({'ref_id':service._id})
    metadatas = {}
    if metadata_parent:
        metadatas = {m['checker']:m for m in metadata_parent.metadata if m['service_id'] == service._id}

    # get rolling ping window
    ping_data = {'good':[], 'bad':[]}
    last_ping = { 'time'               : None,
                  'response_time'      : None,
                  'operational_status' : None }

    pl = db.PingLatest.find_one({'service_id':service._id})
    if pl:
        # set ping data for graph
        latest_pings, latest_statuses = pl.get_current_data()
        for i in xrange(0, len(latest_pings)):
            v = {'x':i, 'y':latest_pings[i] or 50}
            if latest_statuses[i]:
                ping_data['good'].append(v)
                ping_data['bad'].append({'x':i, 'y':0})
            else:
                ping_data['bad'].append(v)
                ping_data['good'].append({'x':i, 'y':0})

        # latest ping info
        last_ping.update({'time':pl.updated,
                          'response_time': pl.last_response_time,
                          'operational_status': pl.last_operational_status})

    return render_template('show_service.html',
                           service=service,
                           ping_data=ping_data,
                           datasets=datasets,
                           last_ping=last_ping,
                           metadatas=metadatas)

@app.route('/services/', methods=['POST'])
@requires_auth
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

@app.route('/services/<ObjectId:service_id>', methods=['POST'])
@requires_auth
def edit_service_submit(service_id):
    f = ServiceForm()
    service = db.Service.find_one({'_id':service_id})

    #@TODO: validation
    f.populate_obj(service)

    url = urlparse.urlparse(service.url)
    service.tld = url.hostname
    service.save()

    flash("Service '%s' updated" % service.name, 'success')
    return redirect(url_for('show_service', service_id=service_id))

@app.route('/services/<ObjectId:service_id>/delete', methods=['POST'])
@requires_auth
def delete_service(service_id):
    service = db.Service.find_one( { '_id' : service_id } )
    service.delete()

    flash("Deleted service %s" % service.name)
    return redirect(url_for('services'))

@app.route('/services/<ObjectId:service_id>/ping', methods=['GET'])
@requires_auth
def ping_service(service_id):
    ret = ping_service_task(service_id)
    flash("Ping returned: %s" % ret)
    return redirect(url_for('show_service', service_id=service_id))

@app.route('/services/<ObjectId:service_id>/harvest', methods=['GET'])
@requires_auth
def harvest_service(service_id):
    s = db.Service.find_one({ '_id' : service_id })

    h = harvest(service_id)
    flash(h)
    return redirect(url_for('show_service', service_id=service_id))

@app.route('/services/<ObjectId:service_id>/start_monitoring', methods=['POST'])
@requires_auth
def start_monitoring_service(service_id):
    s = db.Service.find_one({'_id':service_id})
    assert s is not None

    s.active = True
    s.save()

    flash("Started monitoring the '%s' service" % s.name)
    return redirect(url_for('show_service', service_id=service_id))

@app.route('/services/<ObjectId:service_id>/stop_monitoring', methods=['POST'])
@requires_auth
def stop_monitoring_service(service_id):
    s = db.Service.find_one({'_id':service_id})
    assert s is not None

    s.active = False()
    s.save()

    flash("Stopped monitoring the '%s' service" % s.name)
    return redirect(url_for('show_service', service_id=service_id))

@app.route('/services/<ObjectId:service_id>/start_harvesting', methods=['POST'])
@requires_auth
def start_harvesting_service(service_id):
    s = db.Service.find_one({'_id':service_id})
    assert s is not None

    s.active = True
    s.save()

    flash("Started harvesting the '%s' service" % s.name)
    return redirect(url_for('show_service', service_id=service_id))

@app.route('/services/<ObjectId:service_id>/stop_harvesting', methods=['POST'])
@requires_auth
def stop_harvesting_service(service_id):
    s = db.Service.find_one({'_id':service_id})
    assert s is not None

    s.active = False()
    s.save()

    flash("Stopped harvesting the '%s' service" % s.name)
    return redirect(url_for('show_service', service_id=service_id))

@app.route('/services/<ObjectId:service_id>/edit', methods=['GET'])
@requires_auth
def edit_service(service_id):
    service = db.Service.find_one({'_id':service_id})
    g.title = "Editing " + service.name
    f = ServiceForm(obj=service)
    return render_template('edit_service.html', service=service, form=f)

@app.route('/services/reindex', methods=['GET'])
@requires_auth
def reindex():
    queue.enqueue(reindex_services)
    return jsonify({"message" : "queued"})

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

@app.route('/services/daily', methods=['GET'], defaults={'year':None, 'month':None, 'day':None})
@app.route('/services/daily/<int:year>/<int:month>/<int:day>', methods=['GET'])
def daily(year, month, day):
    end_time = None
    if year is not None and month is not None and day is not None:
        end_time = datetime.strptime("%s/%s/%s" % (year, month, day), "%Y/%m/%d")


    failed_services, services, end_time, start_time = db.Service.get_failures_in_time_range(end_time=end_time)
    g.title = "Daily Report (%s)" % end_time.strftime("%Y-%m-%d")
    return render_template("daily_service_report_page.html", services=services, failed_services=failed_services, start_time=start_time, end_time=end_time)

