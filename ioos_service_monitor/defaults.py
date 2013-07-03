import os
import urlparse

DEBUG = False
TESTING = False
LOG_FILE = True

WEB_PASSWORD = os.environ.get("WEB_PASSWORD")
SECRET_KEY = os.environ.get("SECRET_KEY")

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
MAIL_SENDER = os.environ.get("MAIL_SENDER")