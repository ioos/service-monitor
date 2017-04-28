#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
ioos_catalog/tasks/harvest.py
'''
from bson import ObjectId
from datetime import datetime
from ioos_catalog import app, db, queue
from ioos_catalog.tasks.debug import debug_wrapper
from ioos_catalog.harvesters import context_decorator
from random import shuffle


LARGER_SERVICES = [
    ObjectId('53d34aed8c0db37e0b538fda'),
    ObjectId('53d49c8d8c0db37ff1370308')
]


def queue_harvest_tasks():
    """
    Generate a number of harvest tasks.

    Meant to be called via cron. Only queues services that are active.
    """

    with app.app_context():
        # Some hosts don't like successive repeated connections, so by
        # shuffling our list of services we reduce the liklihood that we'll
        # harvest from the same host enough times to cause a service problem.
        # This should reduce timeouts and unresponsive datasets
        services = list(db.Service.find({'active': True}))
        services = distinct_services(services)
        shuffle(services)
        for s in services:
            service_id = s._id
            if service_id in LARGER_SERVICES:
                continue
            # count all the datasets associated with this particular service
            datalen = db.datasets.find({'services.service_id':
                                        service_id}).count()
            # handle timeouts for services with large numbers of datasets
            if datalen <= 36:
                timeout_secs = 180
            else:
                # for large numbers of requests, 5 seconds should be enough
                # for each request, on average
                timeout_secs = datalen * 60
            queue.enqueue_call(harvest, args=(service_id,),
                               timeout=timeout_secs)

    # record dataset/service metrics after harvest
    add_counts()


def distinct_services(services):
    '''
    Returns a filtered list of services that contain unique URLs. Services with
    duplicate URLs are removed

    :param list services: List of services
    '''
    retval = []
    urls = set()
    for service in services:
        if service.url in urls:
            continue
        urls.add(service.url)
        retval.append(service)
    return retval


def queue_provider(provider):
    with app.app_context():
        services = list(db.Service.find({'data_provider': provider, 'active': True}))
        services = distinct_services(services)
        for s in services:
            service_id = s._id
            if service_id in LARGER_SERVICES:
                continue
            # count all the datasets associated with this particular service
            datalen = db.datasets.find({'services.service_id':
                                        service_id}).count()
            # handle timeouts for services with large numbers of datasets
            if datalen <= 36:
                timeout_secs = 180
            else:
                # for large numbers of requests, 5 seconds should be enough
                # for each request, on average
                timeout_secs = datalen * 60
            queue.enqueue_call(harvest, args=(service_id,),
                               timeout=timeout_secs)

    # record dataset/service metrics after harvest
    add_counts()


def add_counts():
    """Returns a timestamped aggregated count"""
    collection = db.metric_counts
    services_pipeline_ra = [
        {
            '$group': {
                '_id': '$data_provider',
                'count': {
                    '$sum': 1
                },
                'active_count': {
                    '$sum': {
                        '$cond': ['$active', 1, 0]
                    }
                }
            }
        },
        {
            '$project': {
                '_id': 1,
                'count': 1,
                'active_count': 1,
                'inactive_count': {
                    '$subtract': ['$count', '$active_count']
                }
            }
        }
    ]
    services_arr = db.services.aggregate(services_pipeline_ra)['result']

    services_by_ra = collection.MetricCount({'date': datetime.utcnow(),
                                             'stats_type': u'services_by_ra',
                                             'count': services_arr})
    services_by_ra.save()

    services_pipeline_type = [
        {
            '$group': {
                '_id': '$service_type',
                'count': {'$sum': 1},
                'active_count': {
                    '$sum': {
                        '$cond': ['$active', 1, 0]
                    }
                }
            }
        },
        {
            '$project': {
                '_id': 1,
                'count': 1,
                'active_count': 1,
                'inactive_count': {
                    '$subtract': ['$count', '$active_count']
                }
            }
        }
    ]

    services_arr_type = db.services.aggregate(services_pipeline_type)['result']

    services_by_type = collection.MetricCount({'date': datetime.utcnow(),
                                               'stats_type': u'services_by_type',
                                               'count': services_arr_type})
    services_by_type.save()

    # get the total, active, inactive counts per RA for datasets by getting
    # unique data providers in the services array
    # When a dataset is shared between services, count once for each data
    # provider
    datasets_pipeline = [
        {"$unwind": "$services"},
        {
            "$project": {
                "data_provider": '$services.data_provider',
                "active": "$active"
            }
        },
        {
            "$group": {
                "_id": {
                    "_id": "$_id",
                    "data_provider": "$data_provider",
                    "active": "$active"
                }
            }
        },
        {
            "$project": {
                "_id": "$_id._id",
                "data_provider": "$_id.data_provider",
                "active": "$_id.active"
            }
        },
        {
            "$group": {
                "_id": "$data_provider",
                "total_services": {"$sum": 1},
                "active_services": {
                    "$sum": {
                        "$cond": ["$active", 1, 0]
                    }
                }
            }
        },
        {
            "$project": {
                "_id": 1,
                "total_services": 1,
                "active_services": 1,
                "inactive_services": {
                    "$subtract": ["$total_services", "$active_services"]
                }
            }
        }
    ]

    datasets_arr = db.datasets.aggregate(datasets_pipeline)['result']

    datasets_by_ra = collection.MetricCount({'date': datetime.utcnow(),
                                             'stats_type': u'datasets_by_ra',
                                             'count': datasets_arr})
    datasets_by_ra.save()


@debug_wrapper
@context_decorator
def harvest(service_id, ignore_active=False):

    service = db.Service.find_one({'_id': ObjectId(service_id)})

    # Get the harvest or make a new one
    harvest = db.Harvest.find_one({'service_id': ObjectId(service_id)})
    if harvest is None:
        harvest = db.Harvest()
        harvest.service_id = ObjectId(service_id)

    harvest.harvest(ignore_active=ignore_active)
    harvest.save()

    for service in db.Service.find({"url": service.url, "_id": {"$ne": ObjectId(service_id)}}):
        other_harvest = db.Harvest.find_one({'service_id': ObjectId(service._id)})
        if other_harvest is None:
            other_harvest = db.Harvest()
            other_harvest.service_id = ObjectId(service._id)
        elif other_harvest._id == harvest._id:
            continue
        other_harvest.harvest_date = harvest.harvest_date
        other_harvest.harvest_status = harvest.harvest_status
        other_harvest.harvest_successful = harvest.harvest_successful
        other_harvest.harvest_messages = harvest.harvest_messages
        other_harvest.save()
    return harvest.harvest_status


