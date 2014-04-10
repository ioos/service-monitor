from ioos_catalog import app,db
from mongokit import DocumentMigration

# Services
from ioos_catalog.models import service
class ServiceMigration(DocumentMigration):
    # add any migrations here named "allmigration_*"
    def allmigration01__add_harvest_job_id_field(self):
        self.target = {'harvest_job_id':{'$exists': False}}
        self.update = {'$set':{'harvest_job_id': None}}

    def allmigration02__add_ping_job_id_field(self):
        self.target = {'ping_job_id':{'$exists': False}}
        self.update = {'$set':{'ping_job_id': None}}

    def allmigration03__add_active_field(self):
        self.target = {'active':{'$exists': False}}
        self.update = {'$set':{'active':True}}

    def allmigration04__add_manual_field(self):
        self.target = {'manual':{'$exists':False}}
        self.update = {'$set':{'manual':False}}

# Datasets
from ioos_catalog.models import dataset
class DatasetMigration(DocumentMigration):
    # add any migrations here named "allmigration_*"
    pass

with app.app_context():
    migration = ServiceMigration(service.Service)
    migration.migrate_all(collection=db['services'])

    migration = DatasetMigration(dataset.Dataset)
    migration.migrate_all(collection=db['datasets'])

