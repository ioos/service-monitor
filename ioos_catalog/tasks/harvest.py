from bson import ObjectId
from datetime import datetime
from lxml import etree

from owslib.sos import SensorObservationService
from owslib.swe.sensor.sml import SensorML
from owslib.util import testXMLAttribute, testXMLValue
from owslib.crs import Crs

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
                network_ds = SensorML(self.sos.describe_sensor(outputFormat='text/xml;subtype="sensorML/1.0.1/profiles/ioos_sos/1.0"', procedure=uid)).members[0]
                # Iterate over stations in the network and process them individually
                for component in network_ds.components:
                    stat_uid = testXMLAttribute(component, "{http://www.w3.org/1999/xlink}xlink")
                    if stat_uid is not None and stat_uid.split(":")[2] == "station":
                        if not stat_uid in processed:
                            self.process_station(stat_uid)
                        processed.append(stat_uid)

    def process_station(self, uid):
        """ Makes a DescribeSensor request based on a 'uid' parameter being a station procedure """

        GML_NS   = "http://www.opengis.net/gml"
        XLINK_NS = "http://www.w3.org/1999/xlink"

        with app.app_context():

            metadata_value = etree.fromstring(self.sos.describe_sensor(outputFormat='text/xml;subtype="sensorML/1.0.1/profiles/ioos_sos/1.0"', procedure=uid))
            sml_system     = SensorML(metadata_value).members[0]

            unique_id = self.get_named_by_definition(sml_system.get_identifiers_by_name("stationID"), "http://mmisw.org/ont/ioos/definition/stationID")
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

            service = {
                'service_type'      : unicode(self.service_type),
                'service_id'        : ObjectId(self.service_id),
                'metadata_type'     : u'sensorml',
                'metadata_value'    : unicode(etree.tostring(metadata_value))
            }
            dataset.services.append(service)

            # NAME
            name = self.get_named_by_definition(sml_system.get_identifiers_by_name("shortName"), "http://mmisw.org/ont/ioos/definition/shortName")
            if name is None:
                dataset.messages.append(u"Could not get a 'shortName' from the SensorML identifiers.  Looking for a definition of 'http://mmisw.org/ont/ioos/definition/shortName'")
            else:
                dataset.name = unicode(name)

            # DESCRIPTION
            description = self.get_named_by_definition(sml_system.get_identifiers_by_name("longName"), "http://mmisw.org/ont/ioos/definition/longName")
            if description is None:
                dataset.messages.append(u"Could not get a 'longName' from the SensorML identifiers.  Looking for a definition of 'http://mmisw.org/ont/ioos/definition/longName'")
            else:
                dataset.description = unicode(description)

            # PLATFORM TYPE
            platformType = self.get_named_by_definition(sml_system.get_classifiers_by_name("platformType"), "http://mmisw.org/ont/ioos/definition/platformType")
            if platformType is None:
                dataset.messages.append(u"Could not get a 'platformType' from the SensorML identifiers.  Looking for a definition of 'http://mmisw.org/ont/ioos/definition/platformType'")
            else:
                dataset.asset_type  = unicode(platformType)

            # KEYWORDS
            dataset.keywords = map(unicode, sml_system.keywords)

            # LOCATION is in GML
            loc = sml_system.location[0]
            if loc.tag == "{%s}Point" % GML_NS:
                pos_element = loc.find("{%s}pos" % GML_NS)
                # strip out points
                positions = map(float, testXMLValue(pos_element).split(" "))
                crs = Crs(testXMLAttribute(pos_element, "srsName"))
                if crs.axisorder == "yx":
                    dataset.geojson = json.loads(geojson.dumps(geojson.Point([positions[1], positions[0]])))
                else:
                    dataset.geojson = json.loads(geojson.dumps(geojson.Point([positions[0], positions[1]])))
            else:
                dataset.messages.append(u"Found an unrecognized sml:location element and didn't attempt to process: %s" % etree.tostring(loc))

            # VARIABLES (components)
            vs = [unicode(testXMLAttribute(comp, "{%s}title" % XLINK_NS).split(":")[-1]) for comp in sml_system.components]
            dataset.variables = list(set(dataset.variables + vs))

            dataset.updated = datetime.utcnow()
            dataset.save()
            return "Harvested"

    def get_named_by_definition(self, element_list, string_def):
        try:
            return next((st.value for st in element_list if st.definition == string_def))
        except:
            return None


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

