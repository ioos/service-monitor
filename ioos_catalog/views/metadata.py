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
from ioos_catalog.tasks.harvest import harvest

@app.route('/metadata/')
def metadatas():
    metadatas = list(db.Metadata.find())

    sids = set()
    dids = set()
    cols = set()

    for m in metadatas:
        if m.ref_type == 'service':
            sids.add(m.ref_id)

        if m.ref_type == 'dataset':
            dids.add(m.ref_id)

        map(cols.add, m.metamap.iterkeys())

    # get mappings of services/datasets
    services = {s._id:s for s in db.Service.find({'_id':{'$in':list(sids)}})}
    #datasets = {d._id:d.name for d in db.Dataset.find({'_id':{'$in':list(dids)}})}

    return render_template("metadatas.html",
                           metadatas=metadatas,
                           services=services,
                           #datasets=datasets,
                           columns=list(cols))

