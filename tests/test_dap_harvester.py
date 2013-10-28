from ioos_catalog.tasks.harvest import DapHarvest
from tests.flask_mongo import FlaskMongoTestCase
import json

class TestDapHarvester(FlaskMongoTestCase):

    def test_rgrid(self):
        url          = u"http://tds.glos.us/thredds/dodsC/SST/LakeErieSST-Agg"
        service_type = u'DAP'
        self.db['services'].insert({ 'url' : url, 'service_type' : service_type })
        service = list(self.db['services'].find())[0]

        h = DapHarvest(service=service).harvest()

        #assert len(list(self.db["datasets"].find())) == 14

        for d in self.db['datasets'].find():
            # Each dataset should only have one service
            assert len(d['services']) == 1
            s = d['services'][0]
            assert type(json.loads(json.dumps(s['geojson']))) == dict
            assert s['asset_type'] == "RGRID"
            assert sorted(s['keywords']) == sorted([u'GLOS',
                                                    u'MODIS',
                                                    u'LST',
                                                    u'SST',
                                                    u'MTRI',
                                                    u'AOC',
                                                    u'Satellite',
                                                    u'Sea Surface Temperature',
                                                    u'Lake Surface Temperature'])

        d = self.db['datasets'].find({ 'uid' : u'http://tds.glos.us/thredds/dodsC/SST/LakeErieSST-Agg' })[0]
        assert sorted(d['services'][0]['variables']) == sorted([u'http://mmisw.org/ont/cf/parameter/lake_surface_temperature'])

    def test_native_roms_cgrid(self):
        url          = u"http://tds.marine.rutgers.edu/thredds/dodsC/roms/espresso/2013_da/fmrc_t1/his/UNIDATA_FMRC_test_1_Best"
        service_type = u'DAP'
        self.db['services'].insert({ 'url' : url, 'service_type' : service_type })
        service = list(self.db['services'].find())[0]

        h = DapHarvest(service=service).harvest()

        #assert len(list(self.db["datasets"].find())) == 14

        for d in self.db['datasets'].find():
            # Each dataset should only have one service
            assert len(d['services']) == 1
            s = d['services'][0]
            # Can't compute geometry on default ROMS output
            assert s['geojson'] == None
            assert s['asset_type'] == "CGRID"
            assert sorted(s['keywords']) == []
