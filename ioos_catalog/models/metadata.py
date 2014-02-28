from bson.objectid import ObjectId
from datetime import datetime, timedelta

from ioos_catalog.models.base_document import BaseDocument
from ioos_catalog import app, db, scheduler

@db.register
class Metadata(BaseDocument):
    __collection__   = 'metadatas'
    use_dot_notation = True
    use_schemaless   = True

    structure = {
        'ref_id'            : ObjectId, # ref to Service or Dataset
        'ref_type'          : unicode,  # "service" or "dataset"
        'ref_subtype'       : unicode,  # "SOS" or "DS" or "NC" ...

        'cc_score'          : {        # score via compliance checker
            'score'         : float,
            'max_score'     : float,
            'pct'           : float,
        },
        'cc_results'        : [{        # full results of last compliance checker run
            'name'          : unicode,
            'score'         : float,
            'max_score'     : float,
            'weight'        : int,
            'msgs'          : [unicode],
            'children'      : [],     # @TODO
        }],
        'metamap'           : {        # metadata mapping using wicken
        },
        'created'           : datetime,
        'updated'           : datetime,
    }

    default_values = {
        'created': datetime.utcnow
    }

    indexes = [
        {
            'fields': ['ref_id', 'ref_type', 'ref_subtype']
        },
    ]

