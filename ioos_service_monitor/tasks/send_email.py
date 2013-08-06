from flask.ext.mail import Message
from ioos_service_monitor import db, app, mail
from flask import render_template

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

        to_addresses = ["ioos-dmac@asa.flowdock.com"]
        if app.config.get('DEBUG') == False and kwargs['service'].contact is not None:
            to_addresses = kwargs['service'].contact.split(",")

        cc_addresses = ["ioos.catalog@noaa.gov"] if app.config.get('DEBUG') == False else None

        send(subject,
             to_addresses,
             cc_addresses,
             text_template,
             html_template)

