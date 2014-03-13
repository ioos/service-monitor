from ioos_catalog import db
from datetime import datetime, timedelta

now = datetime.utcnow()
lasttwo = now - timedelta(days=14)

p = db.Stat.aggregate([{'$match': {'created':{'$gte': lasttwo}}},
                   {'$group': {'_id': '$service_id',
                               'stid': {'$push':'$_id'}}}])
"""
                               'times': {'$push': '$created'},
                               'pings': {'$push': '$response_time'},
                               'codes': {'$push': '$response_code'},
                               'status': {'$push': '$operational_status'}}}])
"""

for s in p:
    print s['_id']
    pl = db.PingLatest.find_one({'service_id': s['_id']})
    if not pl:
        pl = db.PingLatest()
        pl.service_id = s['_id']

    # grab set of pings
    stats = db.Stat.find({'_id':{'$in':s['stid']}}).sort([('created', 1)])

    for st in stats:
        pl.set_ping_data(st.created, st.response_time, st.response_code, st.operational_status==1)
    #for i in xrange(len(s['times'])-1, 0, -1):
    #    pl.set_ping_data(s['times'][i], s['pings'][i], s['codes'][i], s['status'][i]==1)

    pl.save()

