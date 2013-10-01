from flask.ext.mongokit import Document
from ioos_service_monitor import app, db

class BaseDocument(Document):

    @classmethod
    def aggregate(cls, *args, **kwargs):
        agg_results = db[cls.__collection__].aggregate(*args, **kwargs)

        if 'ok' not in agg_results or not agg_results['ok']:
            raise StandardError("Aggregate failed")

        return agg_results['result']
