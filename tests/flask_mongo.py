import unittest
from ioos_service_monitor import app
from mongokit import Connection

class FlaskMongoTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.raw_app = app
        self.app = app.test_client()
        self.db = Connection(app.config['MONGODB_HOST'], app.config['MONGODB_PORT'])[app.config['MONGODB_DATABASE']]

    def tearDown(self):
        self.db.drop_collection("services")
        self.db.drop_collection("stats")
        self.db.drop_collection("datasets")
