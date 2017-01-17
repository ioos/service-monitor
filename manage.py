from flask.ext.script import Manager

from rq import Queue

from ioos_catalog import app, db, queue, redis_connection

from ioos_catalog.tasks.stat import queue_ping_tasks
from ioos_catalog.tasks.harvest import queue_harvest_tasks, queue_provider
from ioos_catalog.tasks.reindex_services import reindex_services, cleanup_datasets as cleanup
from ioos_catalog.tasks.send_email import send_daily_report_email
from ioos_catalog.tasks.captcha import initialize_captcha_db

manager = Manager(app)

@manager.command
def queue_pings():
    queue_ping_tasks()

@manager.command
def queue_harvests():
    queue_harvest_tasks()

@manager.command
def queue_provider_harvest(provider):
    queue_provider(provider)

@manager.command
def empty_queue():
    queue.empty()

@manager.command
def empty_failed():
    fqueue = Queue('failed', connection=redis_connection)
    fqueue.empty()

@manager.option('--provider', help='Provider to filter')
def queue_reindex(provider=None):
    print provider
    queue.enqueue(reindex_services, provider)

@manager.command
def queue_daily_status():
    queue.enqueue(send_daily_report_email)

@manager.command
def cleanup_datasets():
    queue.enqueue(cleanup)

@manager.command
def migrate_140827():
    from ioos_catalog.models.migration.migrate_140827 import migrate
    queue.enqueue(migrate)

@manager.command
def migrate_140828():
    from ioos_catalog.models.migration.migrate_140828 import migrate
    queue.enqueue(migrate)

@manager.command
def migrate_141008():
    from ioos_catalog.models.migration.migrate_141008 import migrate
    queue.enqueue(migrate)

@manager.command
def migrate_150120():
    from ioos_catalog.models.migration.migrate_150120 import migrate
    queue.enqueue(migrate)

@manager.command
def captcha_init():
    initialize_captcha_db()

@manager.command
def remove_dangle():
    from ioos_catalog.tasks.cleanup import queue_remove_dangle
    queue_remove_dangle()

if __name__ == "__main__":
    manager.run()


