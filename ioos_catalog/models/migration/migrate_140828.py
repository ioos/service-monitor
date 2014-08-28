#!/usr/bin/env python
# coding: utf-8

'''
Migrates:
    - Dataset Names
'''

from bson.objectid import ObjectId
from ioos_catalog.models.service import Service
from ioos_catalog.tasks.harvest import get_common_name
from ioos_catalog import app
from ioos_catalog import db

def migrate_active_datasets():
    datasets = db.Dataset.find({}) # Annoyingly large
    mapping_dict = {
        # Remap UNKNOWN, None to Unspecified
        None: 'Unspecified',
        'UNKNOWN': 'Unspecified',
        '(NONE)': 'Unspecified',
        # Rectangular grids remap to the CF feature type "grid"
        'grid': 'Regular Grid',
        'Grid': 'Regular Grid',
        'GRID': 'Regular Grid',
        'RGRID': 'Regular Grid',
        # Curvilinear grids
        'CGRID': 'Curvilinear Grid',
        # remap some CDM `cdm_data_type`s to equivalent CF-1.6 `featureType`s
        'trajectory': 'Trajectory',
        'point': 'Point',
        # UGrid to unstructured grid
        'ugrid': 'Unstructured Grid',
        # Buoys
        'BUOY': 'Buoy',
        # time series
        'timeSeries': 'Time Series'
    }
    for d in datasets:
        for i,s in enumerate(d['services']):
            if s['asset_type'] != get_common_name(s['asset_type']):
                d['services'][i]['asset_type'] = get_common_name(s['asset_type'])
                app.logger.info("Updating dataset: %s", d['_id'])
                d.save()

def migrate():
    with app.app_context():
        migrate_active_datasets()
        app.logger.info("Migration 2014-08-28 complete")
