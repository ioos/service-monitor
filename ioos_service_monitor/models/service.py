from datetime import datetime
from ioos_service_monitor import app, db
from ioos_service_monitor.models.base_document import BaseDocument

@db.register
class Service(BaseDocument):
    __collection__ = 'services'
    use_dot_notation = True
    use_schemaless = True

    structure = {
        'name'               : unicode, # friendly name of the service
        'url'                : unicode, # url where the service resides
        'tld'                : unicode, # top level domain/ip address for grouping purposes
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

    @classmethod
    def group_by_tld(cls):
        by_tld = cls.aggregate({'$group':{'_id':'$tld', 'ids':{'$addToSet':'$_id'}}})
        return {a['_id']:a['ids'] for a in by_tld}

    def operational_status(self, num_samples=1):
        retval = db.Stat.aggregate([{'$match':{'service_id':self._id}},
                                    {'$sort':{'created':1}},
                                    {'$limit':num_samples},
                                    {'$group':{'_id':None,
                                               'os':{'$avg':'$operational_status'}}}])

        if len(retval) > 0:
            return retval[0]['os']

        return None


    def response_time(self, num_samples=1):
        retval = db.Stat.aggregate([{'$match':{'service_id':self._id}},
                                    {'$sort':{'created':1}},
                                    {'$limit':num_samples},
                                    {'$group':{'_id':None,
                                               'rt':{'$avg':'$response_time'}}}])

        if len(retval) > 0:
            return retval[0]['rt']

        return None

