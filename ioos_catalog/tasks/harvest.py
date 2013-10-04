from bson import ObjectId
from datetime import datetime
from lxml import etree

from owslib.sos import SensorObservationService
from owslib.swe.sensor.sml import SensorML
from owslib.util import testXMLAttribute, testXMLValue
from owslib.crs import Crs

from pyoos.parsers.ioos.describe_sensor import IoosDescribeSensor

import geojson
import json

from ioos_catalog import app, db
from ioos_catalog.tasks.send_email import send_service_down_email

def harvest(service_id):
    with app.app_context():
        service = db.Service.find_one( { '_id' : ObjectId(service_id) } )

        if service.service_type == "DAP":
            return DapHarvest(service._id, service.service_type, service.url).harvest()
        elif service.service_type == "SOS":
            return SosHarvest(service._id, service.service_type, service.url).harvest()
        elif service.service_type == "WMS":
            return WmsHarvest(service._id, service.service_type, service.url).harvest()
        elif service.service_type == "WCS":
            return WcsHarvest(service._id, service.service_type, service.url).harvest()

def unicode_or_none(thing):
    if thing is None:
        return thing
    else:
        try:
            return unicode(thing)
        except:
            return None

class Harvester(object):
    def __init__(self, service_id, service_type, url):
        self.service_id     = service_id
        self.service_type   = service_type
        self.url            = url

class SosHarvest(Harvester):
    def __init__(self, service_id, service_type, url):
        Harvester.__init__(self, service_id, service_type, url)

    def harvest(self):
        self.sos = SensorObservationService(self.url)
        for offering in self.sos.offerings:
            # TODO: We assume an offering should only have one procedure here
            # which will be the case in sos 2.0, but may not be the case right now
            # on some non IOOS supported servers.
            uid = offering.procedures[0]
            sp_uid = uid.split(":")

            # List storing the stations that have already been processed in this SOS server.
            # This is kept and checked later to avoid servers that have the same stations in many offerings.
            processed = []

            # temnplate:  urn:ioos:type:authority:id
            # sample:     ioos:station:wmo:21414
            if sp_uid[2] == "station":   # Station Offering
                if not uid in processed:
                    self.process_station(uid)
                processed.append(uid)
            elif sp_uid[2] == "network": # Network Offering
                network_ds = IoosDescribeSensor(self.sos.describe_sensor(outputFormat='text/xml;subtype="sensorML/1.0.1/profiles/ioos_sos/1.0"', procedure=uid))
                # Iterate over stations in the network and process them individually
                for proc in network_ds.procedures:
                    if proc is not None and proc.split(":")[2] == "station":
                        if not proc in processed:
                            self.process_station(proc)
                        processed.append(proc)

    def process_station(self, uid):
        """ Makes a DescribeSensor request based on a 'uid' parameter being a station procedure """

        GML_NS   = "http://www.opengis.net/gml"
        XLINK_NS = "http://www.w3.org/1999/xlink"

        with app.app_context():

            metadata_value = etree.fromstring(self.sos.describe_sensor(outputFormat='text/xml;subtype="sensorML/1.0.1/profiles/ioos_sos/1.0"', procedure=uid))
            station_ds     = IoosDescribeSensor(metadata_value)

            unique_id = station_ds.id
            if unique_id is None:
                app.logger.warn("Could not get a 'stationID' from the SensorML identifiers.  Looking for a definition of 'http://mmisw.org/ont/ioos/definition/stationID'")
                return

            dataset = db.Dataset.find_one( { 'uid' : unicode(unique_id) } )
            if dataset is None:
                dataset = db.Dataset()
                dataset.uid = unicode(unique_id)

            # Find service reference in Dataset.services and remove (to replace it)
            tmp = dataset.services[:]
            for d in tmp:
                if d['service_id'] == self.service_id:
                    dataset.services.remove(d)

            # Parsing messages
            messages = []

            # NAME
            name = unicode_or_none(station_ds.shortName)
            if name is None:
                service.messages.append(u"Could not get a 'shortName' from the SensorML identifiers.  Looking for a definition of 'http://mmisw.org/ont/ioos/definition/shortName'")

            # DESCRIPTION
            description = unicode_or_none(station_ds.longName)
            if description is None:
                messages.append(u"Could not get a 'longName' from the SensorML identifiers.  Looking for a definition of 'http://mmisw.org/ont/ioos/definition/longName'")

            # PLATFORM TYPE
            asset_type = unicode_or_none(station_ds.platformType)
            if asset_type is None:
                messages.append(u"Could not get a 'platformType' from the SensorML identifiers.  Looking for a definition of 'http://mmisw.org/ont/ioos/definition/platformType'")

            # LOCATION is in GML
            gj = None
            loc = station_ds.location
            if loc is not None and loc.tag == "{%s}Point" % GML_NS:
                pos_element = loc.find("{%s}pos" % GML_NS)
                # strip out points
                positions = map(float, testXMLValue(pos_element).split(" "))
                crs = Crs(testXMLAttribute(pos_element, "srsName"))
                if crs.axisorder == "yx":
                    gj = json.loads(geojson.dumps(geojson.Point([positions[1], positions[0]])))
                else:
                    gj = json.loads(geojson.dumps(geojson.Point([positions[0], positions[1]])))
            else:
                messages.append(u"Found an unrecognized child of the sml:location element and did not attempt to process it: %s" % etree.tostring(loc).strip())

            service = {
                # Reset service
                'name'              : name,
                'description'       : description,
                'service_type'      : self.service_type,
                'service_id'        : ObjectId(self.service_id),
                'metadata_type'     : u'sensorml',
                'metadata_value'    : unicode(etree.tostring(metadata_value)).strip(),
                'messages'          : map(unicode, messages),
                'keywords'          : map(unicode, sorted(station_ds.keywords)),
                'variables'         : map(unicode, sorted(station_ds.variables)),
                'asset_type'        : asset_type,
                'geojson'           : gj,
                'updated'           : datetime.utcnow()
            }

            dataset.services.append(service)
            dataset.updated = datetime.utcnow()
            dataset.save()
            return "Harvested"

class WmsHarvest(Harvester):
    def __init__(self, service_id, service_type, url):
        Harvester.__init__(self, service_id, service_type, url)
    def harvest(self):
        pass

class WcsHarvest(Harvester):
    def __init__(self, service_id, service_type, url):
        Harvester.__init__(self, service_id, service_type, url)
    def harvest(self):
        pass

class DapHarvest(Harvester):
    def __init__(self, service_id, service_type, url):
        Harvester.__init__(self, service_id, service_type, url)

    def harvest(self):
        """
        Identify the type of CF dataset this is:
          * UGRID
          * CGRID
          * RGRID
          * DSG
        """
        pass

