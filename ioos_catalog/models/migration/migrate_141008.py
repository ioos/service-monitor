#!/usr/bin/env python
# coding: utf-8

'''
Migrates:
    - CENCOOS -> CeNCOOS
'''

from ioos_catalog import db, app

def migrate_cencoos():
    # Handle the datasets
    docs = db.Dataset.find({"services.data_provider":"CENCOOS"})
    for doc in docs:
        for services in doc.services:
            if services['data_provider'] == u'CENCOOS':
                services['data_provider'] = u'CeNCOOS'
        app.logger.info("Updated data provider for dataset %s", doc._id)
        doc.save()

    # Handle the services
    docs = db.Service.find({"data_provider":u"CENCOOS"})
    for doc in docs:
        doc['data_provider'] = u'CeNCOOS'
        app.logger.info("Updated data provider for service %s", doc._id)
        doc.save()
    
def migrate():
    with app.app_context():
        migrate_cencoos()
        app.logger.info("Migration 2014-10-08 complete")
    
