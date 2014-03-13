from bson import ObjectId
from collections import defaultdict
from datetime import datetime, timedelta
import pytz
from ioos_catalog import app, db, scheduler
from ioos_catalog.models.base_document import BaseDocument
from ioos_catalog.tasks.stat import ping_service_task
from ioos_catalog.tasks.harvest import harvest

@db.register
class PingLatest(BaseDocument):
    """
    Rolling weekly window of pings by service_id
    """
    __collection__   = 'ping_latest'
    use_dot_notation = True
    use_schemaless   = True

    structure = {
        'service_id'              : ObjectId, # id of the service

        # latest data (last updated timestamp is 'updated' standard field)
        'last_response_time'      : int,      # last ping value
        'last_response_code'      : int,      # last response code
        'last_operational_status' : bool,   # last operational status
        'last_good_time'          : datetime, # last timestamp that the service was alive (possibly null)

        # rolling weekly data
        'response_times'          : [int],    # list of pings, indexed by day of week * 24 + hour
        'response_codes'          : [int],    # list of response codes, indexed by day of week * 24 + hour
        'operational_statuses'    : [bool],   # list of op status, indexed by day of week * 24 + hour

        'created'                 : datetime,
        'updated'                 : datetime,
    }

    default_values = {
        'created'              : datetime.utcnow,
        'response_times'       : [None] * (24*7),
        'response_codes'       : [None] * (24*7),
        'operational_statuses' : [None] * (24*7),
    }

    indexes = [
        {
            'fields': ['service_id', 'updated']
        },
    ]

    def get_index(self, dt):
        weekday = dt.weekday()
        return weekday * 24 + dt.hour

    def set_ping_data(self, dt, response_time, response_code, operational_status):
        # figure number of nulls to set
        # starting with last known update time, go forward an hour until we reach current dt
        start_dt = self.updated
        if start_dt is not None and start_dt > dt:
            # uh wat
            print "badness"
            return

        if start_dt is not None:
            start_dt += timedelta(hours=1)
            while start_dt < dt:
                idx = self.get_index(start_dt)

                self.response_times[idx]       = None
                self.response_codes[idx]       = None
                self.operational_statuses[idx] = None

                start_dt += timedelta(hours=1)

        # set latest
        self.updated = dt
        self.last_response_time = response_time
        self.last_response_code = response_code
        self.last_operational_status = operational_status
        if operational_status:
            self.last_good_time = dt

        # set rolling window
        idx                            = self.get_index(dt)
        self.response_times[idx]       = response_time
        self.response_codes[idx]       = response_code
        self.operational_statuses[idx] = operational_status

        return idx

    def get_current_data(self):
        start_dt = datetime.utcnow()
        idx = self.get_index(start_dt)

        # literally the last entry!
        if idx == 167:
            ret = (self.response_times, self.operational_statuses)
        else:
            start_idx = idx + 1

            ret = (self.response_times[start_idx:168] + self.response_times[0:start_idx],
                   self.operational_statuses[start_idx:168] + self.operational_statuses[0:start_idx])

        return ret



