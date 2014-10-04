#!/usr/bin/env python
from bson import ObjectId
from ioos_catalog import app, db
from ioos_catalog.models.base_document import BaseDocument
from ioos_catalog.tasks.harvest import DapHarvest, SosHarvest, WmsHarvest, WcsHarvest
from datetime import datetime

import requests

@db.register
class Harvest(BaseDocument):
    '''
    Model for a harvest and the reporting of a harvest's status
    '''
    MAX_MESSAGES = 20

    __collection__   = 'harvests'
    use_dot_notation = True
    use_schemaless   = True

    structure = {
        'service_id' : ObjectId,
        'harvest_date' : datetime,
        'harvest_status' : unicode,
        'harvest_messages' : [ {
            'date' : datetime,
            'message' : unicode
        } ]
            
    }

    def harvest(self):

        service_id = self.service_id

        # Get the service
        service = db.Service.find_one( { '_id' : ObjectId(service_id) } )
        if service is None:
            app.log.error("Attempted harvest on invalid service_id: %s" % service_id)
            app.log.error("Deleting harvest record")
            self.delete()
            return

        # make sure service is active before we harvest
        if not service.active:
            #service.cancel_harvest()
            self.new_message("Service %s is not active, not harvesting" % service_id)
            self.set_status("Service is down")
            return

        # ping it first to see if alive
        try:
            _, response_code = service.ping(timeout=15)
            operational_status = True if response_code in [200,400] else False
        except (requests.ConnectionError, requests.HTTPError, requests.Timeout):
            operational_status = False

        if not operational_status:
            # not a failure
            # @TODO: record last attempt time/this message
            self.new_message("Aborted harvest due to service down")
            self.set_status("Service is down")
            return

        try:
            message = ''
            if service.service_type == "DAP":
                message = DapHarvest(service).harvest()
            elif service.service_type == "SOS":
                message = SosHarvest(service).harvest()
            elif service.service_type == "WMS":
                message = WmsHarvest(service).harvest()
            elif service.service_type == "WCS":
                message = WcsHarvest(service).harvest()
            self.new_message(message or 'Successful Harvest')
            self.set_status("Good")
            return
        except Exception as e:
            from traceback import format_exc
            app.logger.exception("Failed harvesting service %s", service)
            self.new_message(format_exc())
            self.set_status("Harvest Failed")
            return

    
    def new_message(self, message):
        if not isinstance(message, unicode):
            message = unicode(message)
        dtg = datetime.utcnow()

        while len(self.harvest_messages) > (self.MAX_MESSAGES-1):
            self.harvest_messages.pop()

        self.harvest_messages.insert(0, {'date' : dtg, 'message' : message})

    def set_status(self, status):
        if not isinstance(status, unicode):
            status = unicode(status)

        self.harvest_status = status
        self.harvest_date = datetime.utcnow()
