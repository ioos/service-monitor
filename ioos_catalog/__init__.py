import os
import datetime
import json
import re
from functools import wraps

from flask import Flask, redirect, request, current_app

__version__ = "3.2.2"
# Create application object
app = Flask(__name__)


from flask_environments import Environments
env = Environments(app)
env.from_yaml('config.yml')

app.config.from_object('ioos_catalog.defaults')

import sys

# Setup RQ Dashboard
from rq_dashboard import RQDashboard
RQDashboard(app)

# Create logging
if app.config.get('LOG_FILE') == True:
    import logging
    from logging import FileHandler
    file_handler = FileHandler('logs/ioos_catalog.txt')
    formatter = logging.Formatter('%(asctime)s - %(process)d - %(name)s - %(module)s:%(lineno)d - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.info('Application Process Started')

# Create the Redis connection
import redis
redis_pool = redis.ConnectionPool(host=app.config.get('REDIS_HOST'),
                                  port=app.config.get('REDIS_PORT'),
                                  db=app.config.get('REDIS_DB'))
redis_connection = redis.Redis(connection_pool=redis_pool)

# rq
from rq import Queue
queue = Queue('default', connection=redis_connection)

# Create the database connection
from flask.ext.mongokit import MongoKit
db = MongoKit(app)
# For captcha
from flask.ext.sqlalchemy import SQLAlchemy
sqlalchemy_db = SQLAlchemy(app)

# Create the Flask-Mail object
from flask.ext.mail import Mail
mail = Mail(app)

# Create datetime jinja2 filter
def datetimeformat(value, format='%a, %b %d %Y at %I:%M%p'):
    if isinstance(value, datetime.datetime):
        return value.strftime(format)
    return value

def timedeltaformat(starting, ending):
    if isinstance(starting, datetime.datetime) and isinstance(ending, datetime.datetime):
        return ending - starting
    return "unknown"

def prettydate(d):
    if d is None:
        return "never"
    utc_dt = datetime.datetime.utcnow()
    #app.logger.info(utc_dt)
    #app.logger.info(d)
    if utc_dt > d:
        return prettypastdate(utc_dt - d, d)
    else:
        return prettyfuturedate(d - utc_dt)

# from http://stackoverflow.com/a/5164027/84732
def prettypastdate(diff, d):
    s = diff.seconds
    if diff.days > 7:
        return d.strftime('%d %b %y')
    elif diff.days > 1:
        return '{} days ago'.format(diff.days)
    elif diff.days == 1:
        return '1 day ago'
    elif s <= 1:
        return 'just now'
    elif s < 60:
        return '{} seconds ago'.format(s)
    elif s < 120:
        return '1 minute ago'
    elif s < 3600:
        return '{} minutes ago'.format(s/60)
    elif s < 7200:
        return '1 hour ago'
    else:
        return '{} hours ago'.format(s/3600)

def prettyfuturedate(diff):
    s = diff.seconds
    if diff.days > 7:
        return d.strftime('%d %b %y')
    elif diff.days > 1:
        return '{} days from now'.format(diff.days)
    elif diff.days == 1:
        return '1 day from now'
    elif s <= 1:
        return 'just now'
    elif s < 60:
        return '{} seconds from now'.format(s)
    elif s < 120:
        return '1 minute from now'
    elif s < 3600:
        return '{} minutes from now'.format(s/60)
    elif s < 7200:
        return '1 hour from now'
    else:
        return '{} hours from now'.format(s/3600)

def is_list(val):
    return isinstance(val, list)

def trim_star(val):
    if val.endswith("*"):
        return val[0:-1]

    return val

def trim_dataset(val):
    try:
        if val.endswith('.nc'):
            matches = re.match(r'^http://.*/([a-zA-Z0-9_ \-]+\.ncd?)$', val)
            return matches.group(1)
        elif val.startswith('http'):
            matches = re.match(r'^https?://.*/(.*)$', val)
            return matches.group(1)
        elif val.startswith('urn'):
            matches = re.match(r'^urn:ioos:station:(.*)$', val)
            return matches.group(1)
    except Exception:
        pass
    return val

app.jinja_env.filters['datetimeformat'] = datetimeformat
app.jinja_env.filters['timedeltaformat'] = timedeltaformat
app.jinja_env.filters['prettydate'] = prettydate
app.jinja_env.filters['is_list'] = is_list
app.jinja_env.filters['trim_star'] = trim_star
app.jinja_env.filters['trim_dataset'] = trim_dataset

# pad/truncate filter (for making text tables)
def padfit(value, size):
    if len(value) <= size:
        return value.ljust(size)

    return value[0:(size-3)] + "..."

app.jinja_env.filters['padfit'] = padfit

def slugify(value):
    """
    Normalizes string, removes non-alpha characters, and converts spaces to hyphens.
    Pulled from Django
    """
    import unicodedata
    import re
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = unicode(re.sub('[^\w\s-]', '', value).strip())
    return unicode(re.sub('[-\s]+', '-', value))

# from https://gist.github.com/aisipos/1094140
def support_jsonp(f):
    """Wraps JSONified output for JSONP"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        callback = request.args.get('callback', False)
        if callback:
            content = str(callback) + '(' + str(f(*args,**kwargs).data) + ')'
            return current_app.response_class(content, mimetype='application/javascript')
        else:
            return f(*args, **kwargs)
    return decorated_function

# basic auth from http://flask.pocoo.org/snippets/8/
from functools import wraps
from flask import request, Response

def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return username == 'admin' and password == app.config.get('WEB_PASSWORD')

def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
        'Admin access required, please login' , 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})

def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated

# Import everything
import ioos_catalog.views
import ioos_catalog.models
import ioos_catalog.tasks

# Captcha
from flask_captcha import Captcha
captcha = Captcha(app)
from flask_captcha.views import captcha_blueprint
app.register_blueprint(captcha_blueprint)


# Mimetype handling
import mimetypes

mimetypes.add_type('image/svg+xml', '.svg')
