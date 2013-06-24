from ioos_service_monitor import app, db
from bson import ObjectId

def ping_service_task(service_id):
    with app.app_context():
        stat = db.Stat()
        stat.service_id=ObjectId(service_id)
        stat.ping_service()
        stat.save()

