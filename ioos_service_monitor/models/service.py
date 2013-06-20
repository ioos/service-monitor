from flask.ext.mongokit import Document
from datetime import datetime
from ioos_service_monitor import app, db

@db.register
class Service(Document):
    __collection__ = 'services'
    use_dot_notation = True
    use_schemaless = True

    structure = {
        'name'               : unicode, # friendly name of the service
        'url'                : unicode, # url where the service resides
        'service_id'         : unicode, # id of the service
        'service_type'       : unicode, # service type
        'data_provider'      : unicode, # who provides the data
        'geophysical_params' : unicode, #
        'contact'            : unicode, # comma separated list of email addresses to contact when down
        'interval'           : int,     # interval (in s) between stat retrievals
        'created'            : datetime,
        'updated'            : datetime,
    }

    default_values = {
        'created': datetime.utcnow
    }

