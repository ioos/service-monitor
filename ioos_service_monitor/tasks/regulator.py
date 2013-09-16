from datetime import datetime, timedelta
from bson.objectid import ObjectId

import pytz

from ioos_service_monitor import app, db, scheduler

from ioos_service_monitor.tasks.stat import ping_service_task
from ioos_service_monitor.tasks.reindex_services import reindex_services
from ioos_service_monitor.tasks.send_email import send_daily_report_email

def regulate():
    with app.app_context():

        # Get services that have not been updated in two weeks and remove them.
        # The reindex job sets the 'updated' field.  The below logic should effectively remove
        # services that the reindex task has not seen in two weeks.
        two_weeks_ago = (datetime.utcnow() - timedelta(weeks=2)).replace(tzinfo=pytz.utc)
        deletes = [s for s in db.Service.find() if s.updated.replace(tzinfo=pytz.utc).astimezone(pytz.utc) < two_weeks_ago]
        for d in deletes:
            d.delete()

        # Get function and args of 
        jobs = scheduler.get_jobs()

        # Make sure a daily report job is running
        daily_email_jobs = [job for job in jobs if job.func == send_daily_report_email]
        if len(daily_email_jobs) > 1:
            # Cancel all but the first daily email job
            for j in daily_email_jobs[1:]:
                scheduler.cancel(j)
        elif len(daily_email_jobs) < 1:
            # Run today at 3am (if it is between midnight and 3am)
            runat = datetime.now().replace(hour=3, minute=0, second=0, microsecond=0)
            if datetime.now() > runat:
                # Run tomorrow at 3am (it is already past 3am)
                runat = runat + timedelta(days=1)

            scheduler.schedule(
                scheduled_time=runat,           # Time for first execution
                func=send_daily_report_email,   # Function to be queued
                interval=86400,                 # Time before the function is called again, in seconds (86400 == 1 day)
                repeat=None,                    # Repeat this number of times (None means repeat forever)
                result_ttl=100000               # How long to keep the results, in seconds
            )

        # Make sure a service update job is running
        reindex_services_jobs = [job for job in jobs if job.func == reindex_services]
        if len(reindex_services_jobs) < 1:
            scheduler.schedule(
                scheduled_time=datetime.now(),  # Time for first execution
                func=reindex_services,          # Function to be queued
                interval=21600,                 # Time before the function is called again, in seconds (21600 == 1/4 of a day)
                repeat=None,                    # Repeat this number of times (None means repeat forever)
                result_ttl=40000,               # How long to keep the results, in seconds
                timeout=1200                    # Default timeout of 180 seconds may not be enough
            )

        # Make sure each service has a ping job
        stat_jobs = [unicode(job.args[0]) for job in jobs if job.func == ping_service_task]

        # Get services that don't have jobs
        services = [s for s in db.Service.find() if unicode(s._id) not in stat_jobs]

        # Schedule the ones that do not
        for s in services:
            job = scheduler.schedule(
                scheduled_time=datetime.now(),  # Time for first execution
                func=ping_service_task,         # Function to be queued
                args=(unicode(s._id),),         # Arguments passed into function when executed
                interval=s.interval,            # Time before the function is called again, in seconds
                repeat=None,                    # Repeat this number of times (None means repeat forever)
                result_ttl=s.interval * 2       # How long to keep the results, in seconds    
            )
            s['job_id'] = unicode(job.id)
            s.save()

        
    return "Regulated %s reindex jobs, %s ping jobs, and deleted %s old services" % (len(reindex_services_jobs), len(stat_jobs), len(deletes))