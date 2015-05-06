#!/usr/bin/env python
from bson import ObjectId
from ioos_catalog import app, db
from ioos_catalog.models.base_document import BaseDocument
from ioos_catalog.tasks.harvest import DapHarvest, SosHarvest, WmsHarvest, WcsHarvest
from lxml.etree import XMLSyntaxError
from datetime import datetime
from traceback import format_exc
from owslib import ows

import requests
import socket

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
        'service_id'         : ObjectId,
        'harvest_date'       : datetime,
        'harvest_status'     : unicode,
        'harvest_successful' : bool,
        'harvest_messages'   : [ {
            'date'       : datetime,
            'successful' : bool,
            'message'    : unicode
        } ]

    }

    def harvest(self, ignore_active=False):

        service_id = self.service_id

        # Get the service
        service = db.Service.find_one( { '_id' : ObjectId(service_id) } )
        if service is None:
            app.log.error("Attempted harvest on invalid service_id: %s" % service_id)
            app.log.error("Deleting harvest record")
            self.delete()
            return

        if ignore_active:
            app.logger.info("Ignoring service active, harvesting anyway")

        # make sure service is active before we harvest
        if not ignore_active and not service.active:
            app.logger.info("Service is down, not harvesting")
            #service.cancel_harvest()
            self.new_message("Service %s is not active, not harvesting" % service_id, False)
            self.set_status("Service is down")
            self.harvest_successful = False
            return

        # ping it first to see if alive
        try:
            _, response_code = service.ping(timeout=60)
            operational_status = True if response_code in [200,400] else False
        except (requests.ConnectionError, requests.HTTPError):
            operational_status = False
            response_code = 0
        except requests.Timeout as e:
            self.new_message("Service Ping Timeout: %s" % e.message, False)
            self.set_status("Timed Out")
            self.harvest_successful = False
            return


        if not operational_status:
            # not a failure
            # @TODO: record last attempt time/this message
            if response_code == 403:
                self.new_message("Permission Denied", False)
                self.set_status("Permission Denied")
            elif response_code == 404:
                self.new_message("Service Not Found, please check the URL", False)
                self.set_status("Not Found")
            else:
                self.new_message("Aborted harvest due to service down", False)
                self.set_status("Service is down")
            self.harvest_successful = False
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
            self.new_message(message or 'Harvest Successful', True)
            self.set_status("Harvest Successful")
            self.harvest_successful = True
            return

        except socket.timeout as e:
            app.logger.exception("Failed to harvest service due to timeout")
            self.new_message("Service Timeout: %s" % e.message, False)
            self.set_status("Timed Out")
            self.harvest_successful = False
            return

        except XMLSyntaxError as e:
            app.logger.exception("Failed harvesting service %s: XMLSyntaxError", service)
            if service.service_type == 'SOS':
                self.set_status("Invalid SOS")
            else:
                self.set_status("Harvest Failed")
            self.harvest_successful = False
            # More descriptive
            self.new_message("Harvester failed to parse the XML response from the SOS endpoint\n\n%s" % format_exc(), False)
            return

        except ows.ExceptionReport as e:
            if 'NULL dataset' in e.message:
                app.logger.exception("Failed to harvest SOS due to NULL Dataset Feature Type Error")
                self.set_status("Harvest Failed: Invalid SOS Response or Invalid URL")
                self.new_message("Harvest Failed: Please check the URL\nThis generally happens when the URL is malformed or the dataset no longer exists.", False)
            elif e.code == 'InvalidParameterValue':
                app.logger.exception("Failed to harvest SOS due to invalid parameter value")
                self.set_status("Harvest Failed: Invalid parameter value. {}".format(e.msg))
                self.new_message("Invalid parameter.  If outputFormat, may indicate difficulty finding the proper outputFormat between IOOS and non-IOOS SensorML implementations")
            elif e.msg == 'No data found for this station':
                app.logger.exception("No data found for station")
                self.set_status(e.msg)
                self.new_message("Harvest Failed: No data found", False)
            else:
                app.logger.exception("Miscellaneous OWSLib exception")
                self.set_status(e.msg)
            self.harvest_successful = False
            return

        except Exception as e:
            app.logger.exception("Failed harvesting service %s", service)
            self.new_message(format_exc(), False)
            self.set_status("Harvest Failed")
            self.harvest_successful = False
            return


    def new_message(self, message, successful):
        if not isinstance(message, unicode):
            message = unicode(message)
        dtg = datetime.utcnow()

        while len(self.harvest_messages) > (self.MAX_MESSAGES-1):
            self.harvest_messages.pop()

        self.harvest_messages.insert(0, {'date' : dtg, 'message' : message, 'successful': successful})

    def set_status(self, status):
        if not isinstance(status, unicode):
            status = unicode(status)

        self.harvest_status = status
        self.harvest_date = datetime.utcnow()


    def success_rate(self):
        '''
        Returns a STRING X/Y, where X is the successes, Y is the attempts
        '''
        attempts = len(self.harvest_messages)
        successes = sum([i.get('successful', False) for i in self.harvest_messages])
        return '%s/%s' % (successes, attempts)

    def get_last_harvests(self, limit_number=30):
        query = [{"$match": {"service_id": self.service_id}},
                 {"$project": {"harvest_messages": 1}},
                 {'$unwind': '$harvest_messages'},
                 {'$project': {'date': '$harvest_messages.date',
                               'successful': "$harvest_messages.successful",
                               'message': "$harvest_messages.message"}},
                 {'$sort': {'date': -1}},
                 {'$limit': limit_number}]

        return db.Harvest.aggregate(query)
