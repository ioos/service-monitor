from ioos_catalog.tasks.harvest import SosHarvest
from tests.flask_mongo import FlaskMongoTestCase
import json

class TestSosHarvester(FlaskMongoTestCase):

    def test_number_of_datasets(self):
        url          = u"http://sos.glos.us/52n/sos/kvp?service=SOS&request=GetCapabilities&AcceptVersions=1.0.0"
        service_type = u'SOS'
        self.db['services'].insert({ 'url' : url, 'service_type' : service_type })
        service = list(self.db['services'].find())[0]

        h = SosHarvest(service=service).harvest()

        #assert len(list(self.db["datasets"].find())) == 14

        for d in self.db['datasets'].find():
            # Each dataset should only have one service
            assert len(d['services']) == 1
            s = d['services'][0]
            assert type(json.loads(json.dumps(s['geojson']))) == dict
            assert s['asset_type'] == "BUOY"
            assert len(s['keywords']) > 0

        d = self.db['datasets'].find({ 'uid' : unicode('urn:ioos:station:us.glos:UMBIO') })[0]
        assert sorted(d['services'][0]['variables']) == sorted([u'urn:ioos:sensor:us.glos:UMBIO:air_pressure_at_sea_level',
                                                                u'urn:ioos:sensor:us.glos:UMBIO:air_temperature',
                                                                u'urn:ioos:sensor:us.glos:UMBIO:dew_point_temperature',
                                                                u'urn:ioos:sensor:us.glos:UMBIO:sea_surface_wave_significant_height',
                                                                u'urn:ioos:sensor:us.glos:UMBIO:sea_surface_wind_wave_period',
                                                                u'urn:ioos:sensor:us.glos:UMBIO:sea_water_temperature',
                                                                u'urn:ioos:sensor:us.glos:UMBIO:wind_from_direction',
                                                                u'urn:ioos:sensor:us.glos:UMBIO:wind_speed',
                                                                u'urn:ioos:sensor:us.glos:UMBIO:wind_speed_of_gust'])