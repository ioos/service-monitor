from datetime import datetime
from ioos_catalog import app, db, queue
from bson import ObjectId
from ioos_catalog.tasks.send_email import send_service_down_email

def ping_service_task(service_id):
    with app.app_context():
        pl = db.PingLatest.get_for_service(ObjectId(service_id))
        _, flip = pl.ping_service()
        pl.save()

        # @TODO: save to WeeklyArchive

        if flip:
            queue.enqueue(send_service_down_email, ObjectId(service_id))
