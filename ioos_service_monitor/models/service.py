from datetime import datetime
from ioos_service_monitor import app, db, scheduler
from ioos_service_monitor.models.base_document import BaseDocument
from ioos_service_monitor.tasks.stat import ping_service_task

@db.register
class Service(BaseDocument):
    __collection__ = 'services'
    use_dot_notation = True
    use_schemaless = True

    structure = {
        'name'                  : unicode, # friendly name of the service
        'url'                   : unicode, # url where the service resides
        'tld'                   : unicode, # top level domain/ip address for grouping purposes
        'service_id'            : unicode, # id of the service
        'service_type'          : unicode, # service type
        'metadata_url'          : unicode,
        'data_provider'         : unicode, # who provides the data
        'geophysical_params'    : unicode, #
        'contact'               : unicode, # comma separated list of email addresses to contact when down
        'interval'              : int,     # interval (in s) between stat retrievals
        'job_id'                : unicode, # id of continuous ping job (scheduled)
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

    def schedule_ping(self):
        """
        Starts a continuous ping job via the rq scheduler.
        Cancels any existing job it can find regarding this service.

        If self.interval is 0 or not set, does nothing.
        """

        self.cancel_ping()

        if not self.interval:
            return None

        job = scheduler.schedule(scheduled_time=datetime.now(),
                                 func=ping_service_task,
                                 args=(unicode(self._id),),
                                 interval=self.interval,
                                 repeat=None,
                                 result_ttl=self.interval * 2)
        self.job_id = unicode(job.id)
        self.save()

        return job.id

    def get_job_id(self):
        for job in scheduler.get_jobs():
            if job.args and isinstance(job.args, tuple) and len(job.args) == 1 and job.args[0] == unicode(self._id):
                return job.id

    def cancel_ping(self):
        """
        Cancels any scheduled ping job for this service.
        """
        try:
            scheduler.cancel(self.job_id)
        except AttributeError:
            # "full nuclear" - make sure there are no other scheduled jobs that are for this service
            try:
                scheduler.cancel(self.get_job_id())
            except BaseException:
                pass
        finally:
            self.job_id = None
            self.save()

