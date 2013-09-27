from ioos_service_monitor.tasks.harvest import SosHarvest
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
            assert d['assetType'] == "BUOY"
            assert len(d['keywords']) > 0

        d = self.db['datasets'].find({ 'uid' : unicode('urn:ioos:station:us.glos:UMBIO') })[0]
        assert sorted(d['variables']) == sorted(['wind_speed','dew_point_temperature','sea_surface_wave_significant_height','wind_from_direction','sea_surface_wind_wave_period','wind_speed_of_gust','sea_water_temperature','air_temperature','air_pressure_at_sea_level'])