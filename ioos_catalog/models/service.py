from collections import defaultdict
from datetime import datetime, timedelta
import pytz
from ioos_catalog import app, db, scheduler
from ioos_catalog.models.base_document import BaseDocument
from ioos_catalog.tasks.stat import ping_service_task
from ioos_catalog.tasks.harvest import harvest

@db.register
class Service(BaseDocument):
    __collection__   = 'services'
    use_dot_notation = True
    use_schemaless   = True

    structure = {
        'name'                  : unicode, # friendly name of the service
        'url'                   : unicode, # url where the service resides
        'tld'                   : unicode, # top level domain/ip address for grouping purposes
        'service_id'            : unicode, # id of the service
        'service_type'          : unicode, # service type
        'metadata_url'          : unicode, # link to raw ISO document the service was pulled from
        'data_provider'         : unicode, # who provides the data
        'contact'               : unicode, # comma separated list of email addresses to contact when down
        'interval'              : int,     # interval (in s) between stat retrievals
        'ping_job_id'           : unicode, # id of continuous ping job (scheduled)
        'harvest_job_id'        : unicode, # id of harvest job (scheduled)
        'created'               : datetime,
        'updated'               : datetime,
    }

    default_values = {
        'created': datetime.utcnow
    }

    @classmethod
    def group_by_tld(cls, filter_ids=None):
        query = [{'$group':{'_id':'$tld', 'ids':{'$addToSet':'$_id'}}}]
        if filter_ids is not None:
            query.insert(0, {'$match':{'_id':{'$in':filter_ids}}})

        by_tld = cls.aggregate(query)
        return {a['_id']:a['ids'] for a in by_tld}

    def schedule_harvest(self, cancel=True):
        """
        Starts a continuous harvest job via the rq scheduler.
        Cancels any existing job it can find regarding this service.

        Runs once per day (86400 seconds)
        """
        if cancel is True:
            self.cancel_harvest()

        job = scheduler.schedule(scheduled_time=datetime.utcnow(),
                                 func=harvest,
                                 args=(unicode(self._id),),
                                 interval=86400,
                                 repeat=None,
                                 timeout=120,
                                 result_ttl=86400 * 2)
        self['harvest_job_id'] = unicode(job.id)
        self.save()

        return job.id

    def schedule_ping(self, cancel=True):
        """
        Starts a continuous ping job via the rq scheduler.
        Cancels any existing job it can find regarding this service.

        If self.interval is 0 or not set, does nothing.
        """

        if cancel is True:
            self.cancel_ping()

        if not self.interval:
            return None

        job = scheduler.schedule(scheduled_time=datetime.utcnow(),
                                 func=ping_service_task,
                                 args=(unicode(self._id),),
                                 interval=self.interval,
                                 repeat=None,
                                 timeout=15,
                                 result_ttl=self.interval * 2)
        self['ping_job_id'] = unicode(job.id)
        self.save()

        return job.id

    def get_ping_job_id(self):
        for job in scheduler.get_jobs():
            if job.func == ping_service_task and unicode(job.args[0]) == unicode(self._id):
                return job.id

    def get_harvest_job_id(self):
        for job in scheduler.get_jobs():
            if job.func == harvest and unicode(job.args[0]) == unicode(self._id):
                return job.id

    def cancel_harvest(self):
        """
        Cancels any scheduled harvest jobs for this service.
        """
        try:
            scheduler.cancel(self.harvest_job_id)
        except AttributeError:
            # "full nuclear" - make sure there are no other scheduled jobs that are for this service
            try:
                scheduler.cancel(self.get_harvest_job_id())
            except BaseException:
                pass
        finally:
            self['harvest_job_id'] = None
            self.save()

    def cancel_ping(self):
        """
        Cancels any scheduled ping job for this service.
        """
        try:
            scheduler.cancel(self.ping_job_id)
        except AttributeError:
            # "full nuclear" - make sure there are no other scheduled jobs that are for this service
            try:
                scheduler.cancel(self.get_ping_job_id())
            except BaseException:
                pass
        finally:
            self['ping_job_id'] = None
            self.save()

    @classmethod
    def count_types(cls):
        retval = db.Service.aggregate([{'$group':{'_id':'$service_type',
                                               'count':{'$sum':1}}}])
        return retval

    @classmethod
    def count_types_by_provider(cls):
        """
        Groups by Service Provider then Service Type.

        MARACOOS ->
            WCS -> 5
            DAP -> 20
        GLOS ->
            SOS -> 57
            ...
        """
        counts = db.Service.aggregate([{'$group':{'_id':{'service_type':'$service_type',
                                                         'data_provider':'$data_provider'},
                                                  'cnt':{'$sum':1}}}])

        # transform into slightly friendlier structure.  could likely do this in mongo but no point
        retval = defaultdict(dict)
        for val in counts:
            retval[val['_id']['data_provider']][val['_id']['service_type']] = val['cnt']

        retval = dict(retval)

        for provider, svc_counts in retval.iteritems():
            retval[provider]['_all'] = sum(svc_counts.itervalues())

        return retval

    @classmethod
    def get_failures_in_time_range(self, end_time=None, start_time=None):

        if end_time is None:
            end_time = datetime.utcnow()
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=pytz.utc)
        end_time = end_time.astimezone(pytz.utc)

        if start_time is None:
            start_time = end_time - timedelta(days=1)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=pytz.utc)
        start_time = start_time.astimezone(pytz.utc)

        service_stats = db.Stat.aggregate([{'$match':{'created':{'$gte':start_time,
                                                                 '$lte':end_time}}},
                                           {'$sort':{'created':1}},
                                           {'$group':{'_id':'$service_id',
                                                      'total': {'$sum':1},
                                                      'status': {'$push':'$operational_status'},
                                                      'current': {'$last':'$operational_status'}}},
                                           {'$unwind':'$status'},
                                           {'$match':{'status':0}},
                                           {'$group':{'_id':'$_id',
                                                      'total':{'$last':'$total'},
                                                      'current':{'$last':'$current'},
                                                      'fails':{'$sum':1}}}])

        failed_services = {x[u'_id']:(x[u'fails'], x[u'total'], x[u'current']) for x in service_stats}

        # retrieve all services
        services = list(db.Service.find({'_id':{'$in':failed_services.keys()}}).sort([('data_provider', 1), ('name', 1)]))

        return failed_services, services, end_time, start_time

