from bson.objectid import ObjectId
from flask.ext.mongokit import Document
from datetime import datetime
from ioos_service_monitor import app, db

@db.register
class Stat(Document):
    __collection__ = 'stats'
    use_dot_notation = True
    use_schemaless = True

    structure = {
        'service_id'         : ObjectId, # reference to service this statistic is for
        'response_time'      : int,      # response time in ms
        'operational_status' : int,      # 1: online 0: offline
        'created'            : datetime,
        'updated'            : datetime,
    }

    default_values = {
        'created': datetime.utcnow
    }

