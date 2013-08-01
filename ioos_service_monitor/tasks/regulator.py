from datetime import datetime
from bson.objectid import ObjectId

from ioos_service_monitor import app, db, scheduler

from ioos_service_monitor.tasks.stat import ping_service_task
from ioos_service_monitor.tasks.reindex_services import reindex_services

def regulate():
    with app.app_context():

        # Get function and args of 
        jobs = scheduler.get_jobs()

        # Make sure a service update job is running
        reindex_services_jobs = [job for job in jobs if job.func == reindex_services]
        if len(reindex_services_jobs) < 1:
            scheduler.schedule(
                scheduled_time=datetime.now(),  # Time for first execution
                func=reindex_services,          # Function to be queued
                interval=21600,                 # Time before the function is called again, in seconds (21600 == 1/4 of a day)
                repeat=None,                    # Repeat this number of times (None means repeat forever)
                result_ttl=40000                # How long to keep the results, in seconds
            )

        # Make sure each service has a ping job
        stat_jobs = [unicode(job.args[0]) for job in jobs if job.func == ping_service_task]

        # Get services that don't have jobs
        services = [s for s in db.Service.find() if unicode(s._id) not in stat_jobs]

        # Schedule the ones that do not
        for s in services:
            scheduler.schedule(
                scheduled_time=datetime.now(),  # Time for first execution
                func=ping_service_task,         # Function to be queued
                args=(unicode(s._id),),         # Arguments passed into function when executed
                interval=s.interval,            # Time before the function is called again, in seconds
                repeat=None,                    # Repeat this number of times (None means repeat forever)
                result_ttl=s.interval * 2       # How long to keep the results, in seconds    
            )
        
    return "Regulated %s reindex jobs and %s ping jobs" % (len(reindex_services_jobs), len(stat_jobs))