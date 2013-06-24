from bson.objectid import ObjectId
from flask.ext.mongokit import Document
from datetime import datetime
from ioos_service_monitor import app, db
import requests

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

    def ping_service(self):
        from ioos_service_monitor.defaults import MONGODB_DATABASE
        print db.connected, MONGODB_DATABASE

        s = db.Service.find_one({'_id':self.service_id})
        assert s is not None

        r = requests.get(s.url)

        self.response_time = r.elapsed.microseconds / 1000
        self.operational_status = 1 if r.status_code == 200 else 0

        return str(self)



