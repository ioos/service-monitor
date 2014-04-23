import os
import urlparse

DEBUG = False
TESTING = False
LOG_FILE = True
JSONIFY_PRETTYPRINT_REGULAR = False

WEB_PASSWORD = os.environ.get("WEB_PASSWORD")
SECRET_KEY = os.environ.get("SECRET_KEY")
SERVER_NAME = os.environ.get("SERVER_NAME", None)

# Database
MONGO_URI = os.environ.get('MONGO_URI')
url = urlparse.urlparse(MONGO_URI)
MONGODB_HOST = url.hostname
MONGODB_PORT = url.port
MONGODB_USERNAME = url.username
MONGODB_PASSWORD = url.password
MONGODB_DATABASE = url.path[1:]

# Redis
REDIS_URI = os.environ.get('REDIS_URI')
url = urlparse.urlparse(REDIS_URI)
REDIS_HOST = url.hostname
REDIS_PORT = url.port
REDIS_USERNAME = url.username
REDIS_PASSWORD = url.password
REDIS_DB = url.path[1:]

# Email
MAIL_SERVER = os.environ.get("MAIL_SERVER")
MAIL_PORT = os.environ.get("MAIL_PORT")
MAIL_USE_TLS = bool(os.environ.get("MAIL_USE_TLS", True))
MAIL_USE_SSL = bool(os.environ.get("MAIL_USE_SSL", False))
MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")

MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER")

# If False, mails are sent to the 'contact' defined for the service, else mails are sent to MAIL_DEFAULT_TO
MAILER_DEBUG = os.environ.get("MAILER_DEBUG", True)

# For services with no contact, use this.  Also use this if MAILER_DEBUG is True
MAIL_DEFAULT_TO = os.environ.get("MAIL_DEFAULT_TO")

# Email to receive daily reports and to be CCd in status reports.  Only used if MAILER_DEBUG is False.
MAIL_DEFAULT_LIST = os.environ.get("MAIL_DEFAULT_LIST")
