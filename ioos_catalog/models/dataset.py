from collections import defaultdict
from datetime import datetime

from bson.objectid import ObjectId

from ioos_catalog import db,app
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
        'services'      : [         # The services that this dataset is available in
            {
                'name'              : unicode,
                'description'       : unicode,
                'service_id'        : ObjectId,   # reference to the service object
                'service_type'      : unicode,    # service type cached here
                'data_provider'     : unicode,    # service data_prodiver cached here
                'metadata_type'     : unicode,    # sensorml, ncml, iso, wmsgetcaps
                'metadata_value'    : unicode,    # value of the metadata (actual xml)
                'keywords'          : [unicode],  # Search keywords
                'variables'         : [unicode],  # Environmental properties measured by this dataset
                'asset_type'        : unicode,    # See the IOOS vocablary for assets: http://mmisw.org/orr/#http://mmisw.org/ont/ioos/platform
                'geojson'           : dict,       # GeoJSON of the datasets location (point / line / polygon) as a dict
                'messages'          : [unicode],    # messages regarding the harvesting of this
                'created'           : datetime,
                'updated'           : datetime
            }
        ],
        'created'       : datetime,
        'updated'       : datetime
    }

    default_values = {
        'created': datetime.utcnow
    }

    @classmethod
    def count_types(cls):
        retval = db.Dataset.aggregate([{'$group':{'_id':'$services.asset_type',
                                               'count':{'$sum':1}}}])
        return retval

    @classmethod
    def count_types_by_provider(cls):
        """
        Groups by Service Provider then Service Type.

        MARACOOS ->
            WCS -> 5
            DAP -> 20
        GLOS ->
            SOS -> 57
            ...
        """
        counts = db.Dataset.aggregate([{'$group':{'_id':{'asset_type':'$services.asset_type',
                                                         'data_provider':'$services.data_provider'},
                                                  'cnt':{'$sum':1}}}])

        # transform into slightly friendlier structure.  could likely do this in mongo but no point
        retval = defaultdict(dict)
        for val in counts:
            try:
                retval[val['_id']['data_provider'][0]][val['_id']['asset_type'][0]] = val['cnt']
            except:
                pass

        return dict(retval)
