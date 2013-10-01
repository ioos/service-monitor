from flask.ext.mail import Message
from ioos_catalog import db, app, mail
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

        subject = "[ioos] Service Status Alert (%s): %s (%s)" % ("UP" if kwargs['status'] else "DOWN", kwargs['service'].name, kwargs['service'].service_type)

        text_template = render_template("service_status_changed.txt", **kwargs)
        html_template = render_template("service_status_changed.html", **kwargs)

        to_addresses = [app.config.get("MAIL_DEFAULT_LIST")] if app.config.get('MAILER_DEBUG') == False else [app.config.get("MAIL_DEFAULT_TO")]
        # Don't send these until Anna updates the ISO document in GeoPortal with the correct service contacts
        #if app.config.get('MAILER_DEBUG') == False and kwargs['service'].contact is not None:
        #    to_addresses = kwargs['service'].contact.split(",")
        cc_addresses = [app.config.get("MAIL_DEFAULT_TO")]

        send(subject,
             to_addresses,
             cc_addresses,
             text_template,
             html_template)

def send_daily_report_email(end_time=None, start_time=None):
    with app.app_context():

        failed_services, services, end_time, start_time = db.Service.get_failures_in_time_range(end_time, start_time)

        text_template = render_template("daily_service_report.txt",
                                        services=services,
                                        failed_services=failed_services,
                                        start_time=start_time,
                                        end_time=end_time)
        html_template = render_template("daily_service_report_email.html",
                                        services=services,
                                        failed_services=failed_services,
                                        start_time=start_time,
                                        end_time=end_time)

        to_addresses = [app.config.get("MAIL_DEFAULT_LIST")] if app.config.get('MAILER_DEBUG') == False else [app.config.get("MAIL_DEFAULT_TO")]
        cc_addresses = [app.config.get("MAIL_DEFAULT_TO")]
        subject      = "[ioos] Service Daily Downtime Report"

        send(subject,
             to_addresses,
             cc_addresses,
             text_template,
             html_template)

