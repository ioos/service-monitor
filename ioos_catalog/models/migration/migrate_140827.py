#!/usr/bin/env python
# coding: utf-8
'''
Migrates to new provider naming
'''


from ioos_catalog.models.service import Service
from ioos_catalog import app
from ioos_catalog import db


def migrate_names():
    changing_providers = {
        'NOS/CO-OPS' : u'NOAA-CO-OPS',
        'USGS/CMGP'  : u'USGS-CMGP',
        'NDBC'       : u'NOAA-NBDC'
    }
    
    services = db.Service.find({'data_provider':{'$in':['NOS/CO-OPS', 'NDBC', 'USGS/CMGP']}})
    for s in services:
        app.logger.info("Renaming provider for %s", s['url'])
        s['data_provider'] = changing_providers[s['data_provider']]
        s.save()

    datasets = db.Dataset.find({'services.data_provider':{'$in':['NOS/CO-OPS', 'NDBC', 'USGS/CMGP']}})
    for d in datasets:
        changed = False
        for i,s in enumerate(d['services']):
            if s['data_provider'] in changing_providers:
                d['services'][i]['data_provider'] = changing_providers[s['data_provider']]
                changed = True
        if changed:
            app.logger.info('Renaming provider in dataset %s', d['uid'])
            d.save()


def migrate_active_datasets():
    datasets = db.Dataset.find({'active':False})
    for d in datasets:
        services = d['services'] # a list of services
        service_ids = [s['service_id'] for s in services]
        # Get the service object
        for service_id in service_ids:
            related_services = db.Service.find({'_id':service_id})
            for service in related_services:
                if service['active']:
                    app.logger.info('Activating %s', d['uid'])
                    d['active'] = True
                    d.save()
                    break
            else:
                continue
            break



def migrate():
    with app.app_context():
        migrate_names()
        migrate_active_datasets()





