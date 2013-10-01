from datetime import datetime

from bson.objectid import ObjectId

from ioos_catalog import db
from ioos_catalog.models.base_document import BaseDocument

@db.register
class Dataset(BaseDocument):
    """
    A Dataset is defined as:
        * Numerical model run
            - Aggregated Forecast, ie all GLERL GLCFS Forecast runs
            - Aggregated Nowcast, ie all GLERL GLCFS Nowcast runs
            - Aggregated Satellite passes, ie. MTRI's  SST for Lake Michigan
            - Specifid Hindcast run/runs, ie. "Hurricane Sandy Run"

        * Physical piece of deployed hardware:
            - Buoy(s) at the same or very similar locations through many deployments
            - A single glider mission (deployment and retrieval).
            - A sampling location that is revisited periodically to take additional measurements
    """

    __collection__   = 'datasets'
    use_dot_notation = True
    use_schemaless   = True

    structure = {
        'uid'           : unicode,
        'name'          : unicode,
        'description'   : unicode,
        'services'      : [            # The services that this dataset is available in
            {
                'service_id'        : ObjectId,   # reference to the service object
                'service_type'      : unicode,    # service type cached here
                'metadata_type'     : unicode,    # sensorml, ncml, iso, wmsgetcaps
                'metadata_value'    : unicode     # value of the metadata (actual xml)
            }
        ],
        'keywords'      : [unicode],   # Search keywords
        'variables'     : [unicode],   # Environmental properties measured by this dataset
        'asset_type'     : unicode,    # See the IOOS vocablary for assets: http://mmisw.org/orr/#http://mmisw.org/ont/ioos/platform
        'geojson'       : dict,        # GeoJSON of the datasets location (point / line / polygon) as a dict
        'messages'      : [unicode],   # Useful messages to display about a dataset
        'created'       : datetime,
        'updated'       : datetime
    }

    default_values = {
        'created': datetime.utcnow
    }


    @classmethod
    def count_types(cls):
        retval = db.Dataset.aggregate([{'$group':{'_id':'$asset_type',
                                               'count':{'$sum':1}}}])
        return retval

