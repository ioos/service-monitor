#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
ioos_catalog/harvesters/__init__.py

Utility functions for the harvesters
'''
from functools import wraps
from ioos_catalog import app


def context_decorator(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        with app.app_context():
            return f(*args, **kwargs)
    return wrapper


def unicode_or_none(thing):
    try:
        if thing is None:
            return thing
        else:
            try:
                return unicode(thing)
            except:
                return None
    except:
        return None


def get_common_name(data_type):
    """Map names from various standards to return a human readable form"""
    # TODO: should probably split this into DAP and SOS specific mappings
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

    # Get the common name if defined, otherwise return initial value
    return unicode(mapping_dict.get(data_type, data_type))
