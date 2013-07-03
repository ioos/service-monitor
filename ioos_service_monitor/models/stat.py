from bson.objectid import ObjectId
from datetime import datetime
import time
from ioos_service_monitor import app, db
from ioos_service_monitor.models.base_document import BaseDocument
import requests
from bson.code import Code

@db.register
class Stat(BaseDocument):
    __collection__ = 'stats'
    use_dot_notation = True
    use_schemaless = True

    structure = {
        'service_id'         : ObjectId, # reference to service this statistic is for
        'response_time'      : int,      # response time in ms
        'operational_status' : int,      # 1: online 0: offline
        'created'            : datetime,
        'updated'            : datetime,
    }

    default_values = {
        'created': datetime.utcnow
    }
    
    def ping_service(self):
        s = db.Service.find_one({'_id':self.service_id})
        assert s is not None

        r = requests.get(s.url)

        self.response_time = r.elapsed.microseconds / 1000
        self.operational_status = 1 if r.status_code in [200,400] else 0

        return str(self)

    @classmethod
    def latest_stats_by_service(self, num_samples=None):
        map_func = Code("""
            function () { emit(this.service_id, {a:[this]}) }
        """)

        red_func = Code("""
            function(k, v) {
              var val = {a:[]}
              v.forEach(function(vv) {
                val.a = vv.a.concat(val.a);
              })

              val.a.sort(function(a, b) {
                return (a.created < b.created) ? 1 : -1;
              })

              val.a = val.a.slice(0, %d);

              return val;
            }
        """ % num_samples)

        res = db["stats"].map_reduce(map_func, red_func, "aggregate_stats_by_tld")
        retval = {a[u'_id']:{'response_time':sum(filter(None,[b.get('response_time',None) for b in a['value']['a']]))/float(len(a['value']['a'])),
                             'operational_status':sum(filter(None,[b.get('operational_status',None) for b in a['value']['a']]))/float(len(a['value']['a'])),
                             'created':max([b.get('created',None) for b in a['value']['a']])} for a in res.find()}
        return retval

    @classmethod
    def latest_stats_by_service_by_time(self, start_time=None, end_time=None, time_delta=None):
        if end_time is None:
            end_time = datetime.utcnow()

        if start_time is None:
            if time_delta is not None:
                start_time = end_time - time_delta
            else:
                start_time = datetime.utcfromtimestamp(0)   # 1970

        # make javascript happy by converting to ms
        start_time = time.mktime(start_time.timetuple()) * 1000
        end_time = time.mktime(end_time.timetuple()) * 1000

        map_func = Code("""
            function () { 
                var d1 = new Date(%s);
                var d2 = new Date(%s);
                if (this.created >= d1 && this.created <= d2) {
                    emit(this.service_id, {a:[this]})
                }
            }
        """ % (start_time, end_time))

        red_func = Code("""
            function(k, v) {
              var val = {a:[]}
              v.forEach(function(vv) {
                val.a = vv.a.concat(val.a);
              })

              val.a.sort(function(a, b) {
                return (a.created < b.created) ? 1 : -1;
              })

              return val;
            }
        """)

        res = db["services"].map_reduce(map_func, red_func, "aggregate_stats_by_tld")
        retval = {a[u'_id']:{'response_time':sum(filter(None,[b.get('response_time',None) for b in a['value']['a']]))/float(len(a['value']['a'])),
                             'operational_status':sum(filter(None,[b.get('operational_status',None) for b in a['value']['a']]))/float(len(a['value']['a'])),
                             'created':max([b.get('created',None) for b in a['value']['a']])} for a in res.find()}
        return retval
