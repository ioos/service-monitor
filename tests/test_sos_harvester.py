from ioos_catalog.tasks.harvest import SosHarvest
from tests.flask_mongo import FlaskMongoTestCase
import json

class TestSosHarvester(FlaskMongoTestCase):

    def test_number_of_datasets(self):
        url          = "http://sos.glos.us/52n/sos/kvp?service=SOS&request=GetCapabilities&AcceptVersions=1.0.0"
        service_type = 'SOS'
        self.db['services'].insert({ 'url' : url, 'service_type' : service_type })
        service = list(self.db['services'].find())[0]

        h = SosHarvest(service_id=service['_id'], url=url, service_type=service_type).harvest()

        #assert len(list(self.db["datasets"].find())) == 14

        for d in self.db['datasets'].find():
            # Each dataset should only have one service
            assert len(d['services']) == 1
            assert type(json.loads(json.dumps(d['geojson']))) == dict
            assert d['asset_type'] == "BUOY"
            assert len(d['keywords']) > 0

        d = self.db['datasets'].find({ 'uid' : unicode('urn:ioos:station:us.glos:UMBIO') })[0]
        assert sorted(d['variables']) == sorted([u'urn:ioos:sensor:us.glos:UMBIO:air_pressure_at_sea_level',
                                                 u'urn:ioos:sensor:us.glos:UMBIO:air_temperature',
                                                 u'urn:ioos:sensor:us.glos:UMBIO:dew_point_temperature',
                                                 u'urn:ioos:sensor:us.glos:UMBIO:sea_surface_wave_significant_height',
                                                 u'urn:ioos:sensor:us.glos:UMBIO:sea_surface_wind_wave_period',
                                                 u'urn:ioos:sensor:us.glos:UMBIO:sea_water_temperature',
                                                 u'urn:ioos:sensor:us.glos:UMBIO:wind_from_direction',
                                                 u'urn:ioos:sensor:us.glos:UMBIO:wind_speed',
                                                 u'urn:ioos:sensor:us.glos:UMBIO:wind_speed_of_gust'])