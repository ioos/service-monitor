import os

from flask import Flask
from flask.ext.mongokit import MongoKit

import datetime

# Create application object
app = Flask(__name__)

app.config.from_object('ioos_service_monitor.defaults')
app.config.from_envvar('APPLICATION_SETTINGS', silent=True)

import sys

# Setup RQ Dashboard
from rq_dashboard import RQDashboard
RQDashboard(app)

# Create logging
if app.config.get('LOG_FILE') == True:
    import logging
    from logging import FileHandler
    file_handler = FileHandler('logs/ioos_service_monitor.txt')
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)

# Create the Redis connection
import redis
from rq_scheduler import Scheduler
redis_connection = redis.from_url(app.config.get("REDIS_URI"))
scheduler = Scheduler('stats', connection=redis_connection)

# Create the database connection
db = MongoKit(app)

# Create datetime jinja2 filter
def datetimeformat(value, format='%a, %b %d %Y at %I:%M%p'):
    if isinstance(value, datetime.datetime):
        return value.strftime(format)
    return value

def timedeltaformat(starting, ending):
    if isinstance(starting, datetime.datetime) and isinstance(ending, datetime.datetime):
        return ending - starting
    return "unknown"

app.jinja_env.filters['datetimeformat'] = datetimeformat
app.jinja_env.filters['timedeltaformat'] = timedeltaformat

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
import ioos_service_monitor.views
import ioos_service_monitor.models
import ioos_service_monitor.tasks

