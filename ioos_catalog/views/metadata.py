import json
import urlparse
import csv
from StringIO import StringIO
from datetime import datetime, timedelta
from pymongo import DESCENDING
from flask.ext.wtf import Form
from flask import render_template, redirect, url_for, request, flash, jsonify, Response, make_response
from wtforms import TextField, IntegerField, SelectField

from ioos_catalog import app, db, scheduler
from ioos_catalog.models.stat import Stat
from ioos_catalog.tasks.stat import ping_service_task
from ioos_catalog.tasks.reindex_services import reindex_services
from ioos_catalog.tasks.harvest import harvest

def get_service_ids(filters=None):
    """
    Gets a list of service ids to be used with get_metadatas.

    By default will find all active services. If you specify your own filters, this won't occur.
    """
    if filters is None:
        filters = {'active':True}

    services = db.Service.find(filters, {'_id':True})
    return [s._id for s in services]

def get_metadatas(service_ids, filters=None):
    """
    Helper method to get metadatas to be transformed/outputted by routed methods below.

    You're required to pass in a list of service ids you want to get metadata for (see get_service_ids).

    Filters are applied to the Metadata query. The filters will always include the passed in list of services.

    Returns 3-tuple of metadata dicts, columns (random order), and dataset ids.
    """

    if filters is None:
        filters = {}

    filters['metadata.service_id'] = {'$in':service_ids}

    db_metadatas = db.Metadata.find(filters)

    dids = set()
    cols = set()

    # promote metadata array inside each metadata object into a full representation
    metadatas = []

    for m in db_metadatas:
        if m.ref_type == 'dataset':
            dids.add(m.ref_id)

        mdict = dict(m)
        for s in m.metadata:
            # our query above returns all Metadata top level documents that have ANY matching service_ids
            # so we need to skip any that aren't in this list
            if s['service_id'] not in service_ids:
                continue

            mdict.update(s['metamap'])
            metadatas.append(mdict)

            map(cols.add, s['metamap'].iterkeys())

    # #####
    # @TODO HACK ALERT
    # #####

    # metamap does not preserve column order. We duplicate the list of cols here according t the asset_sos_map google doc.
    # IF THE MAPPING CHANGES THIS WILL BREAK.
    cols = ['Service Provider Name',
            'Service Contact Name',
            'Service Contact Email',
            'Service Type Name',
            'Service Type Version',
            'Data Format Template Version',
            'Station ID',
            'Station Description',
            'Station WMO ID',
            'Station Short Name',
            'Station Long Name',
            'Station Location Lat',
            'Station Location Lon',
            'RA/Federal Affiliation',
            'Platform Type',
            'Time Period',
            'Platform Sponsor',
            'Operator Name',
            'Operator Email',
            'Operator Sector',
            'Station Publisher Name',
            'Station Publisher Email',
            'Variable Names*',
            'Variable Units*',
            'Altitude Units*',
            'Observed Variable*',
            'Observed Variable Time Last*']

    return metadatas, cols, list(dids)

@app.route('/metadata/')
def metadatas():
    sids = get_service_ids()
    metadatas, cols, dids = get_metadatas(sids)

    # get mappings of services/datasets
    services = {s._id:s for s in db.Service.find({'_id':{'$in':list(sids)}})}
    #datasets = {d._id:d.name for d in db.Dataset.find({'_id':{'$in':list(dids)}})}

    return render_template("metadatas.html",
                           metadatas=metadatas,
                           services=services,
                           #datasets=datasets,
                           columns=list(cols))

@app.route('/metadata/csv/', defaults={'filter_provider':None}, methods=['GET'])
@app.route('/metadata/csv/<path:filter_provider>', methods=['GET'])
def metadatas_csv(filter_provider):

    service_filters = {}
    if filter_provider is not None:
        service_filters['data_provider'] = filter_provider

    sids = get_service_ids(service_filters)
    metadatas, cols, dids = get_metadatas(sids)

    # get mappings of services/datasets
    #services = {s._id:s for s in db.Service.find({'_id':{'$in':list(sids)}})}
    #datasets = {d._id:d.name for d in db.Dataset.find({'_id':{'$in':list(dids)}})}

    output = StringIO()
    writer = csv.DictWriter(output, list(cols), extrasaction='ignore')

    writer.writeheader()

    def sanitize(r):
        return {k:",".join((str(vv) for vv in v)) if isinstance(v, list) else v for k, v in r.iteritems()}

    writer.writerows(map(sanitize, metadatas))

    response = make_response(output.getvalue())
    response.headers['Content-type'] = 'text/csv'
    response.headers['Content-disposition'] = 'attachment; filename=inventory.csv'
    return response

