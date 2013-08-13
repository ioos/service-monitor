from datetime import datetime
from ioos_service_monitor import app, db, scheduler
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
            scheduler.schedule(
                scheduled_time=datetime.now(),
                func=send_service_down_email,
                repeat=1,
                result_ttl=2000
            )

