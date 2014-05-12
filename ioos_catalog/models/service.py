from collections import defaultdict
from datetime import datetime, timedelta
import pytz
import requests
import urllib
import urlparse

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
        'active'                : bool,    # should this service be pinged/harvested?
        'manual'                : bool,    # if True, don't allow reindex to control active flag, it means
                                           # administrator controls active flag manually
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

        Harvest task will not run if the service is not active.

        Runs once per day (86400 seconds)
        """
        if cancel is True:
            self.cancel_harvest()

            # if we cancelled and we know we aren't active, don't bother scheduling
            if not self.active:
                return

        # we only harvest DAP/SOS at the time being, don't waste job time here
        if self.service_type not in ['DAP', 'SOS']:
            return

        timeout = 600

        job = scheduler.schedule(scheduled_time=datetime.utcnow(),
                                 func=harvest,
                                 args=(unicode(self._id),),
                                 interval=86400,
                                 repeat=None,
                                 timeout=timeout,
                                 result_ttl=86400 * 2)
        self['harvest_job_id'] = unicode(job.id)
        self.save()

        return job.id

    def ping(self, timeout=None):
        """
        Performs a service ping.

        Returns a 2-tuple of response time in ms, response code.
        """
        url = self.url
        if self.service_type == 'DAP':
            url += '.das'       # get a description of the data back from OPeNDAP (this gives proper http codes)
        elif self.service_type == 'SOS':
            # modify url to request specific subsection - a ping does not care about data, just that it works
            p                 = list(urlparse.urlparse(url))
            qdict             = dict(urlparse.parse_qsl(p[4]))        # parse_qs gives us lists back, we don't want that here
            qdict['sections'] = 'ServiceIdentification'
            p[4]              = urllib.urlencode(qdict)

            url               = urlparse.urlunparse(p)

        r = requests.get(url, timeout=timeout)

        response_time = r.elapsed.microseconds / 1000
        response_code = r.status_code

        return response_time, response_code

    def schedule_ping(self, cancel=True):
        """
        Starts a continuous ping job via the rq scheduler.
        Cancels any existing job it can find regarding this service.

        Ping task will not run if the service is not active.

        If self.interval is 0 or not set, does nothing.
        """

        if cancel is True:
            self.cancel_ping()

            # if we cancelled and we know we aren't active, don't bother scheduling
            if not self.active:
                return

        if not self.interval:
            return None

        job = scheduler.schedule(scheduled_time=datetime.utcnow(),
                                 func=ping_service_task,
                                 args=(unicode(self._id),),
                                 interval=self.interval,
                                 repeat=None,
                                 timeout=30,
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
        retval = db.Service.aggregate([{'$match': {'active':True}},
                                       {'$group':{'_id':'$service_type',
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
        counts = db.Service.aggregate([{'$match': {'active':True}},
                                       {'$group':{'_id':{'service_type':'$service_type',
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

        # can only support last 7 days with rolling window
        aet = datetime.utcnow() - timedelta(days=7)
        aet = aet.replace(tzinfo=pytz.utc)

        if start_time < aet:
            #raise ValueError("Can't support time more than 7 days ago")
            return {}, [], end_time, start_time

        # get all PLs
        pls = db.PingLatest.find({}, {'service_id':1,
                                      'last_operational_status': 1,
                                      'operational_statuses': 1,
                                      'last_good_time': 1})

        failed_services = {}

        for p in pls:

            sidx = p.get_index(start_time)
            eidx = p.get_index(end_time)

            if sidx < eidx:
                statuses = p.operational_statuses[sidx:eidx]
            else:
                statuses = p.operational_statuses[sidx:168] + p.operational_statuses[0:eidx]

            count = 0
            good = 0
            for s in statuses:
                if s is not None:
                    count+=1
                    if s:
                        good+=1

            if count == good:
                continue

            failed_services[p.service_id] = (good, count, p.last_operational_status)

        # retrieve all services
        services = list(db.Service.find({'_id':{'$in':failed_services.keys()}}).sort([('data_provider', 1), ('name', 1)]))

        return failed_services, services, end_time, start_time

