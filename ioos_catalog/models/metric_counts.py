from datetime import datetime

from bson.objectid import ObjectId

from ioos_catalog import db,app
from ioos_catalog.models.base_document import BaseDocument

@db.register
class MetricCount(BaseDocument):
    """
    Count of a certain metric
    """

    __collection__   = 'metric_counts'
    use_dot_notation = True
    use_schemaless   = True

    structure = {
        'date': datetime,        # snapshot date this was taken
        'stats_type': unicode,        # How is the data aggregated?
        'count': [
            {
                '_id': unicode,
                'count': int,
                'active_count': int,
                'inactive_count': int
            }
        ]
    }
