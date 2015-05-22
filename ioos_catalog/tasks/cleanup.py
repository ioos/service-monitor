#!/usr/bin/env python
'''
ioos_catalog/tasks/cleanup.py

Cleanup tasks for catalog. Removes dangling resources.
'''

from ioos_catalog import app, db, queue
from functools import wraps

def with_app_ctxt(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        with app.app_context():
            return f(*args, **kwargs)
    return wrapper


@with_app_ctxt
def queue_remove_dangle():
    '''
    Queues the job to remove dangling dataset resources
    '''
    queue.enqueue_call(remove_dangling_datasets)



@with_app_ctxt
def remove_dangling_datasets():
    '''
    Prunes all dangling datasets
    '''
    for dataset in db.Dataset.find({}):
        prune_services(dataset)

def prune_services(dataset):
    '''
    Removes stale services from the dataset OR removes the dataset if there are
    no viable services remaining.
    '''
    bad_services = []

    for service_dict in dataset.services:
        service_id = service_dict['service_id']

        valid_service = db.Service.find_one({'_id' : service_id, 'active':True})
        # The first thing to do is remove this from the list as viable services
        if valid_service is None:
            app.logger.critical("DANGLING DATASET %s", dataset._id)
            bad_services.append(service_id)

    if bad_services:
        good_services = [s for s in dataset.services if s['service_id'] not in bad_services]
        app.logger.info("Setting services to")
        app.logger.info(good_services)
        if not good_services:
            app.logger.info("Deleting stale dataset: %s", dataset._id)
            dataset.delete()
        else:
            dataset.services = good_services
            dataset.save()
