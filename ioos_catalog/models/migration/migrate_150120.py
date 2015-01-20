from ioos_catalog import db, app

def migrate():
    """Changes 'Glider_DAC_2' services to 'Glider_DAC'"""
    with app.app_context():
        db.Service.collection.update({"data_provider": u"Glider_DAC_2"},
                                     {'$set': {"data_provider": u"Glider_DAC"}},
                                     multi=True)
        app.logger.info("Migration 2015-01-20 complete")
