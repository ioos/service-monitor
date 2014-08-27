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
        'active'  : bool,
        'created' : datetime,
        'updated' : datetime
    }

    default_values = {
        'created': datetime.utcnow
    }

    @classmethod
    def count_types(cls):
        # @TODO this doesn't do as expected, see count_types_by_provider instead
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
        # intersect with active services only
        service_ids = [s._id for s in db.Service.find({'active':True}, {'_id':1})]
        counts = db.Dataset.aggregate([
            { '$match' : {'services.service_id':{'$in':service_ids}}},
            { '$unwind' : '$services' },
            { '$group' : { '_id' : {'asset_type' : '$services.asset_type',
                                    'data_provider' : '$services.data_provider'},
                          'cnt'  : {'$sum':1}}},
            { '$group' : { '_id' : '$_id.data_provider',
                          'stuff' : {'$addToSet': { 'asset_type' : '$_id.asset_type', 'cnt': '$cnt'}}}}
        ])

        # massage this a bit
        retval = {d['_id']:{dd['asset_type']:dd['cnt'] for dd in d['stuff']} for d in counts}

        # add _all
        for provider, dscounts in retval.iteritems():
            retval[provider]['_all'] = sum(dscounts.itervalues())

        return retval

    @classmethod
    def count_types_by_provider_flat(cls):
        """
        Flattens out list of types by provider.
        """
        counts = cls.count_types_by_provider()

        ret_val = []

        for data_provider, typecounts in counts.iteritems():
            for asset_type, count in typecounts.iteritems():
                if asset_type == '_all':
                    continue

                ret_val.append({'data_provider': data_provider,
                                'asset_type' : asset_type or "(NONE)",
                                'cnt': count})

        return ret_val

