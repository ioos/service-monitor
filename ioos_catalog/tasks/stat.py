from datetime import datetime
from ioos_catalog import app, db, queue
from bson import ObjectId
from ioos_catalog.tasks.send_email import send_service_down_email

def ping_service_task(service_id):
    with app.app_context():

        pl = db.PingLatest.get_for_service(ObjectId(service_id))
        wasnew, flip = pl.ping_service()
        pl.save()

        # save to WeeklyArchive
        if wasnew:
            utcnow = datetime.utcnow()
            pa = db.PingArchive.get_for_service(ObjectId(service_id), utcnow)
            pa.add_ping_data(pl.last_response_time, pl.last_operational_status)
            pa.updated = utcnow
            pa.save()

        if flip:
            queue.enqueue(send_service_down_email, ObjectId(service_id))

        return pl.last_response_time

def queue_ping_tasks():
    """
    Generate a number of ping tasks.

    Meant to be called via cron. Only queues services that are active.
    """
    with app.app_context():
        sids = [s._id for s in db.Service.find({'active':True}, {'_id':True})]
        for sid in sids:
            queue.enqueue(ping_service_task, sid)

