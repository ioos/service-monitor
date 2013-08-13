from flask.ext.mail import Message
from ioos_service_monitor import db, app, mail
from flask import render_template
from collections import defaultdict
from datetime import datetime, timedelta

def send(subject, recipients, cc_recipients, text_body, html_body):
    # sender comes from MAIL_DEFAULT_SENDER in env
    msg = Message(subject, recipients=recipients, cc=cc_recipients)
    msg.body = text_body
    msg.html = html_body
    mail.send(msg)

def send_service_down_email(service_id):
    with app.app_context():
        kwargs = {'service' : db.Service.find_one({'_id':service_id}),
                  'stat'    : db.Stat.find_one({'service_id':service_id}, sort=[('created',-1)]),
                  'last_success_stat' : db.Stat.find_one({'service_id':service_id, 'operational_status':1}, sort=[('created',-1)]) }
        kwargs['status'] = kwargs['stat'].operational_status

        subject = "Service Status Alert (%s): %s (%s)" % ("UP" if kwargs['status'] else "DOWN", kwargs['service'].name, kwargs['service'].service_type)

        text_template = render_template("service_status_changed.txt", **kwargs)
        html_template = render_template("service_status_changed.html", **kwargs)

        to_addresses = app.config.get("MAIL_DEFAULT_TO")
        if app.config.get('MAILER_DEBUG') == False and kwargs['service'].contact is not None:
            to_addresses = kwargs['service'].contact.split(",")

        cc_addresses = [app.config.get("MAIL_DEFAULT_LIST")] if app.config.get('MAILER_DEBUG') == False else None

        send(subject,
             to_addresses,
             cc_addresses,
             text_template,
             html_template)

def send_daily_report_email(end_time=None, start_time=None):
    with app.app_context():


        if end_time is None:
            end_time = datetime.utcnow()
        if end_time.tzinfo is None:
            end_time.replace(tzinfo=pytz.utc)
        end_time = end_time.astimezone(pytz.utc)            

        if start_time is None:
            start_time = end_time - timedelta(days=1)
        if start_time.tzinfo is None:
            start_time.replace(tzinfo=pytz.utc)
        start_time = start_time.astimezone(pytz.utc)

        service_stats = db.Stat.aggregate([{'$match':{'created':{'$gte':start_time,
                                                                 '$lte':end_time}}},
                                           {'$sort':{'created':1}},
                                           {'$group':{'_id':'$service_id',
                                                      'total': {'$sum':1},
                                                      'status': {'$push':'$operational_status'},
                                                      'current': {'$last':'$operational_status'}}},
                                           {'$unwind':'$status'},
                                           {'$match':{'status':0}},
                                           {'$group':{'_id':'$_id',
                                                      'total':{'$last':'$total'},
                                                      'current':{'$last':'$current'},
                                                      'fails':{'$sum':1}}}])

        failed_services = {x[u'_id']:(x[u'fails'], x[u'total'], x[u'current']) for x in service_stats}

        # retrieve all services
        services = list(db.Service.find({'_id':{'$in':failed_services.keys()}}).sort([('data_provider', 1), ('name', 1)]))

        text_template = render_template("daily_service_report.txt",
                                        services=services,
                                        failed_services=failed_services,
                                        start_time=start_time,
                                        end_time=end_time)
        html_template = render_template("daily_service_report.html",
                                        services=services,
                                        failed_services=failed_services,
                                        start_time=start_time,
                                        end_time=end_time)

        to_addresses = [app.config.get("MAIL_DEFAULT_LIST")] if app.config.get('MAILER_DEBUG') == False else [app.config.get("MAIL_DEFAULT_TO")]
        subject      = "Service Daily Downtime Report"

        send(subject,
             to_addresses,
             None,
             text_template,
             html_template)

