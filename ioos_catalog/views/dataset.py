import json
import urlparse
from datetime import datetime, timedelta
from pymongo import DESCENDING
from flask.ext.wtf import Form
from flask import render_template, redirect, url_for, request, flash, jsonify, Response, g, make_response
from wtforms import TextField, IntegerField, SelectField
from urllib import urlencode
from collections import OrderedDict
from bson import json_util, ObjectId
from copy import copy

from ioos_catalog import app, db, requires_auth
from ioos_catalog.models.stat import Stat
from ioos_catalog.tasks.stat import ping_service_task
from ioos_catalog.tasks.reindex_services import reindex_services


class DatasetFilterForm(Form):
    asset_type = SelectField('Asset Type')

@app.route('/datasets/', defaults={'filter_provider':None, 'filter_type':None}, methods=['GET'])
@app.route('/datasets/filter/', defaults={'filter_provider':None, 'filter_type':None}, methods=['GET'])
@app.route('/datasets/filter/<path:filter_provider>', defaults={'filter_type':None}, methods=['GET'])
@app.route('/datasets/filter/<path:filter_provider>/', defaults={'filter_type':None}, methods=['GET'])
@app.route('/datasets/filter/<path:filter_provider>/<filter_type>', methods=['GET'])
@app.route('/datasets/filter/<path:filter_provider>/<filter_type>/', methods=['GET'])
def datasets(filter_provider, filter_type):
    # only get datasets that are active for this list!
    service_ids = [s._id for s in db.Service.find({'active':True}, {'_id':1})]
    filters = {'services.service_id':{'$in':service_ids}}
    titleparts = []

    if filter_provider is not None and filter_provider != "none":
        titleparts.append(filter_provider)
        filters['services.data_provider'] = {'$in': filter_provider.split(',')}

    if filter_type is not None and filter_type != "none":
        titleparts.append(filter_type)

        # @TODO: pretty hacky
        if filter_type == "(NONE)":
            filter_type = None

        filters['services.asset_type'] = {'$in' : filter_type.split(',')}

    # build title
    titleparts.append("Datasets")
    g.title = " ".join(titleparts)

    f        = DatasetFilterForm()
    datasets = list(db.Dataset.find(filters))
    datasets = map(dict, datasets)
    for dataset in datasets:
        if dataset['services']:
            dataset['data_provider'] = dataset['services'][0]['data_provider']
            dataset['name'] = dataset['services'][0]['name'] or 'None'
        else:
            dataset['data_provider'] = 'None'
            dataset['name'] = 'None'
    try:
        # find all service ids with an associated active service endpoint
        assettypes = (db.Dataset.find({'services.service_id':
                                       {'$in': service_ids}},
                                      {'services.asset_type': True})
                                      .distinct('services.asset_type'))
    except:
        assettypes = []

    # get list of unique providers in system
    providers = db["services"].distinct('data_provider')
    return render_template('datasets.html', datasets=datasets, form=f, assettypes=assettypes, providers=providers, filters=filters)

@app.route('/datasets/<ObjectId:dataset_id>', defaults={'oformat':None})
@app.route('/datasets/<ObjectId:dataset_id>/<oformat>', methods=['GET'])
def show_dataset(dataset_id, oformat):
    dataset = db.Dataset.find_one({'_id':dataset_id})

    g.title = dataset.uid

    # get cc/metamap
    metadata_parent = db.Metadata.find_one({'ref_id':dataset._id})

    for s in dataset.services:
        s['geojson'] = json.dumps(s['geojson'])
        s['metadata'] = {}
        if metadata_parent:
            s['metadata'] = {m['checker']:m for m in metadata_parent.metadata if m['service_id'] == s['service_id']}

    if oformat == 'json':
        resp = json.dumps(dataset, default=json_util.default)
        return Response(resp, mimetype='application/json')

    return render_template('show_dataset.html', dataset=dataset)

@app.route('/datasets/removeall', methods=['GET'])
@requires_auth
def removeall():
    dataset = db.Dataset.find()
    for d in dataset:
        d.delete()
    return redirect(url_for('datasets'))

def build_links(item_count, current_page, page_limit, query={}):
    '''
    https://github.com/davidcelis/api-pagination
    http://tools.ietf.org/html/rfc5988
    '''
    base_url = request.url.split('?')[0]
    query = query or {}
    links = []
    last_page_count = item_count / page_limit
    if current_page < last_page_count:
        links.append(build_link(base_url, query, current_page+2, 'next'))
    links.append(build_link(base_url, query, 1, 'first'))
    if current_page > 0:
        links.append(build_link(base_url, query, current_page, 'prev'))
    links.append(build_link(base_url, query, last_page_count-1, 'last'))
    return links

def build_link(base_url, query, page, rel):
    query['page'] = page
    return '<%s>; rel="%s"' % (build_url(base_url, query), rel)


def build_url(url, query):
    if query:
        url += '?' + urlencode(query)
    return url

@app.route('/api/dataset', methods=['GET'])
def get_datasets():
    page_limit = 20
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    search_term = request.args.get('search', None)
    provider = request.args.get('data_provider', None)
    query = {}
    page_query = {}
    if search_term:
        query['$text'] = {'$search' : search_term, '$language' : 'en'}
        page_query['search'] = search_term
    if provider:
        query['services.data_provider'] = provider
        page_query['data_provider'] = provider

    cursor = db.Dataset.find(query, {"services.metadata_value":0})

    if page < 1:
        page = 1
    page = page - 1
    start = (cursor.count() / page_limit) * page
    datasets = list(cursor[start:start+page_limit])
    response = {
        'datasets' : datasets,
        'length' : len(datasets)
    }

    links = build_links(cursor.count(), page, page_limit, page_query)
    response = make_response(json.dumps(response, default=json_util.default))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    response.headers['Link'] = ', '.join(links)
    return response


@app.route('/api/dataset/<string:dataset_id>', methods=['GET'])
def get_dataset(dataset_id):
    try:
        dataset_id = ObjectId(dataset_id)
    except:
        return jsonify(error="ValueError", message="Invalid ObjectId"), 400

    dataset = db.Dataset.find_one({"_id":dataset_id})
    if dataset is None:
        return jsonify(error="NotFound", message="No dataset for this id"), 404
    response = make_response(json.dumps(dataset, default=json_util.default))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response

