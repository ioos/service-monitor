from datetime import datetime
from ioos_service_monitor import app, db, queue
from bson import ObjectId
from ioos_service_monitor.tasks.send_email import send_service_down_email

def ping_service_task(service_id):
    with app.app_context():
        # get last for this service
        last_stat = db.Stat.find_one({'service_id':ObjectId(service_id)}, sort=[('created',-1)])

        stat = db.Stat()
        stat.service_id=ObjectId(service_id)
        stat.ping_service()
        stat.save()

        if last_stat and last_stat.operational_status != stat.operational_status:
            queue.enqueue(send_service_down_email, ObjectId(service_id))
