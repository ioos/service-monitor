from tests.flask_mongo import FlaskMongoTestCase
from uuid import uuid4
from flask import url_for

class TestServices(FlaskMongoTestCase):

    def test_add_service(self):
        slug = unicode(uuid4())[0:6]
        self.app.post('/services/', data={'name':slug})

        req = self.app.get('/services/')
        assert slug in req.data

    def test_delete_service(self):
        slug = unicode(uuid4())[0:6]
        self.app.post('/services/', data={'name':slug})

        # have to get the id out of the db to delete it
        s = self.db['services'].find_one({'name':slug})
        assert s is not None

        self.app.post('/services/%s/delete' % s['_id'])

        s2 = self.db['services'].find_one({'name':slug})
        assert s2 is None


