from bson import ObjectId
from collections import defaultdict
from datetime import datetime, timedelta, time
import pytz
from ioos_catalog import app, db
from ioos_catalog.models.base_document import BaseDocument
from ioos_catalog.tasks.stat import ping_service_task
from ioos_catalog.tasks.harvest import harvest
import requests

@db.register
class PingArchive(BaseDocument):
    """
    Weekly archive of summary ping data (response time, uptime) by service id.
    """
    __collection__   = 'ping_archive'
    use_dot_notation = True
    use_schemaless   = True

    structure = {
        'service_id'              : ObjectId, # id of the service

        'start_time'              : datetime, # pointing to midnight monday of each week

        'num_entries'             : int,      # number of entries
        'response_time_sum'       : int,      # sum of all response_times this week
        'operational_status_sum'  : int,      # sum of all operational statuses (1s and 0s)

        'created'                 : datetime,
        'updated'                 : datetime,
    }

    default_values = {
        'created'                 : datetime.utcnow,
        'num_entries'             : 0,
        'response_time_sum'       : 0,
        'operational_status_sum'  : 0,
    }

    indexes = [
        {
            'fields': ['service_id']
        },
    ]

    @classmethod
    def get_for_service(cls, service_id, dt):
        """
        Returns or creates a new PingArchive for a given service id and datetime.

        A new one will not be saved automatically.
        """
        start_time = datetime.combine((dt - timedelta(days=dt.weekday())).date(), time())
        pa = db.PingArchive.find_one({'service_id':service_id,
                                      'start_time':start_time})
        if not pa:
            pa = db.PingArchive()
            pa.service_id = service_id
            pa.start_time = start_time

        return pa

    def add_ping_data(self, response_time, operational_status):
        self.num_entries += 1
        self.response_time_sum += response_time or 0
        self.operational_status_sum += (1 if operational_status else 0)

    @property
    def response_time(self):
        if self.num_entries == 0:
            return 0

        return self.response_time_sum / float(self.num_entries)

    @property
    def operational_status(self):
        """
        Uptime percentage.
        """
        if self.num_entries == 0:
            return 0

        return self.operational_status_sum / float(self.num_entries)

