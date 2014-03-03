import os
import datetime

from flask import Flask

# Create application object
app = Flask(__name__)

app.config.from_object('ioos_catalog.defaults')
app.config.from_envvar('APPLICATION_SETTINGS', silent=True)

import sys

# Setup RQ Dashboard
from rq_dashboard import RQDashboard
RQDashboard(app)

# Create logging
if app.config.get('LOG_FILE') == True:
    import logging
    from logging import FileHandler
    file_handler = FileHandler('logs/ioos_catalog.txt')
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)

# Create the Redis connection
import redis
from rq import Queue
from rq_scheduler import Scheduler
redis_connection = redis.from_url(app.config.get("REDIS_URI"))
queue = Queue('default', connection=redis_connection)
scheduler = Scheduler('default', connection=redis_connection)

# Create the database connection
from flask.ext.mongokit import MongoKit
db = MongoKit(app)

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

app.jinja_env.filters['datetimeformat'] = datetimeformat
app.jinja_env.filters['timedeltaformat'] = timedeltaformat
app.jinja_env.filters['prettydate'] = prettydate
app.jinja_env.filters['is_list'] = is_list
app.jinja_env.filters['trim_star'] = trim_star

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

# Import everything
import ioos_catalog.views
import ioos_catalog.models
import ioos_catalog.tasks
