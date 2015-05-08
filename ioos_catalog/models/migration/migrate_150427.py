from ioos_catalog import db, app

def migrate():
    """Adds min and max time to datasets"""
    with app.app_context():
        datasets = db.Dataset.find()
        for d in datasets:
            for i, s in enumerate(d['services']):
                d['services'][i]['time_min'] = None
                d['services'][i]['time_max'] = None
            d.save()

