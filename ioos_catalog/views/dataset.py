import json
import urlparse
from datetime import datetime, timedelta
from pymongo import DESCENDING
from flask.ext.wtf import Form
from flask import render_template, redirect, url_for, request, flash, jsonify, Response
from wtforms import TextField, IntegerField, SelectField

from ioos_catalog import app, db, scheduler
from ioos_catalog.models.stat import Stat
from ioos_catalog.tasks.stat import ping_service_task
from ioos_catalog.tasks.reindex_services import reindex_services


class DatasetFilterForm(Form):
    asset_type = SelectField('Asset Type')

@app.route('/datasets/', defaults={'filter_provider':None, 'filter_type':None}, methods=['GET'])
@app.route('/datasets/filter/<filter_provider>/<filter_type>', methods=['GET'])
def datasets(filter_provider, filter_type):
    filters = {}

    if filter_provider is not None and filter_provider != "null":
        filters['services.data_provider'] = filter_provider

    if filter_type is not None and filter_type != "null":
        filters['services.asset_type'] = filter_type

    f          = DatasetFilterForm()
    datasets   = list(db.Dataset.find(filters))
    try:
        assettypes = map(lambda x: x['_id'][0], db.Dataset.aggregate({'$group' : {'_id' : '$services.asset_type' }}))
    except:
        assettypes = []

    # get list of unique providers in system
    providers = db["services"].distinct('data_provider')
    return render_template('datasets.html', datasets=datasets, form=f, assettypes=assettypes, providers=providers, filters=filters)

@app.route('/datasets/<ObjectId:dataset_id>', methods=['GET'])
def show_dataset(dataset_id):
    dataset = db.Dataset.find_one({'_id':dataset_id})
    for s in dataset.services:
        s['geojson'] = json.dumps(s['geojson'])

    # get cc/metamap
    metadata = db.Metadata.find_one({'ref_id':dataset._id})

    return render_template('show_dataset.html', dataset=dataset, metadata=metadata)

@app.route('/datasets/removeall', methods=['GET'])
def removeall():
    dataset = db.Dataset.find()
    for d in dataset:
        d.delete()
    return redirect(url_for('datasets'))
