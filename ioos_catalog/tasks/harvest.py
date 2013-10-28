from bson import ObjectId
from datetime import datetime
from lxml import etree
import itertools

from owslib.sos import SensorObservationService
from owslib.swe.sensor.sml import SensorML
from owslib.util import testXMLAttribute, testXMLValue
from owslib.crs import Crs

from pyoos.parsers.ioos.describe_sensor import IoosDescribeSensor
from paegan.cdm.dataset import CommonDataset, _possiblet, _possiblez, _possiblex, _possibley
from petulantbear.netcdf2ncml import *

from shapely.geometry import mapping, box

import geojson
import json

from ioos_catalog import app, db
from ioos_catalog.tasks.send_email import send_service_down_email

def harvest(service_id):
    with app.app_context():
        service = db.Service.find_one( { '_id' : ObjectId(service_id) } )

        if service.service_type == "DAP":
            return DapHarvest(service).harvest()
        elif service.service_type == "SOS":
            return SosHarvest(service).harvest()
        elif service.service_type == "WMS":
            return WmsHarvest(service).harvest()
        elif service.service_type == "WCS":
            return WcsHarvest(service).harvest()

def unicode_or_none(thing):
    try:
        if thing is None:
            return thing
        else:
            try:
                return unicode(thing)
            except:
                return None
    except:
        return None

class Harvester(object):
    def __init__(self, service):
        self.service = service

class SosHarvest(Harvester):
    def __init__(self, service):
        Harvester.__init__(self, service)

    def harvest(self):
        self.sos = SensorObservationService(self.service.get('url'))
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
                if d['service_id'] == self.service.get('_id'):
                    dataset.services.remove(d)

            # Parsing messages
            messages = []

            # NAME
            name = unicode_or_none(station_ds.shortName)
            if name is None:
                messages.append(u"Could not get a 'shortName' from the SensorML identifiers.  Looking for a definition of 'http://mmisw.org/ont/ioos/definition/shortName'")

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
                'service_type'      : self.service.get('service_type'),
                'service_id'        : ObjectId(self.service.get('_id')),
                'data_provider'     : self.service.get('data_provider'),
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
    def __init__(self, service):
        Harvester.__init__(self, service)
    def harvest(self):
        pass

class WcsHarvest(Harvester):
    def __init__(self, service):
        Harvester.__init__(self, service)
    def harvest(self):
        pass

class DapHarvest(Harvester):

    def __init__(self, service):
        Harvester.__init__(self, service)

    def get_standard_variables(self, dataset):
        for d in dataset.variables:
            try:
                yield dataset.variables[d].getncattr("standard_name")
            except AttributeError:
                pass

    def harvest(self):
        """
        Identify the type of CF dataset this is:
          * UGRID
          * CGRID
          * RGRID
          * DSG
        """

        METADATA_VAR_NAMES = ['crs']
        STD_AXIS_NAMES     = ['latitude', 'longitude', 'time']

        cd = CommonDataset.open(self.service.get('url'))

        # For DAP, the unique ID is the URL
        unique_id = self.service.get('url')

        with app.app_context():
            dataset = db.Dataset.find_one( { 'uid' : unicode(unique_id) } )
            if dataset is None:
                dataset = db.Dataset()
                dataset.uid = unicode(unique_id)

        # Find service reference in Dataset.services and remove (to replace it)
        tmp = dataset.services[:]
        for d in tmp:
            if d['service_id'] == self.service.get('_id'):
                dataset.services.remove(d)

        # Parsing messages
        messages = []

        # NAME
        name = None
        try:
            name = unicode_or_none(cd.nc.getncattr('title'))
        except AttributeError:
            messages.append(u"Could not get dataset name.  No global attribute named 'title'.")

        # DESCRIPTION
        description = None
        try:
            description = unicode_or_none(cd.nc.getncattr('summary'))
        except AttributeError:
            messages.append(u"Could not get dataset description.  No global attribute named 'summary'.")

        # KEYWORDS
        keywords = []
        try:
            keywords = sorted(map(lambda x: unicode(x.strip()), cd.nc.getncattr('keywords').split(",")))
        except AttributeError:
            messages.append(u"Could not get dataset keywords.  No global attribute named 'keywords' or was not comma seperated list.")

        # VARIABLES
        prefix    = ""
        # Add additonal prefix mappings as they become available.
        try:
            standard_name_vocabulary = unicode(cd.nc.getncattr("standard_name_vocabulary"))

            cf_regex = [re.compile("CF-"), re.compile('http://www.cgd.ucar.edu/cms/eaton/cf-metadata/standard_name.html')]

            for reg in cf_regex:
                if reg.match(standard_name_vocabulary) is not None:
                    prefix = "http://mmisw.org/ont/cf/parameter/"
                    break
        except AttributeError:
            pass

        std_names = [x for x in self.get_standard_variables(cd.nc) if x not in STD_AXIS_NAMES]
        variables = []
        if prefix == "":
            variable = map(unicode, cd.nc.variables)
            messages.append(u"Could not find a standard name vocabulary.  No global attribute named 'standard_name_vocabulary'.  All variables included.")
        else:
            variables = ["%s%s" % (prefix, x) for x in std_names]

        # LOCATION (from Paegan)
        # Try POLYGON and fall back to BBOX
        if len(std_names) > 0:
            var_to_get_geo_from = cd.get_varname_from_stdname(next(x for x in std_names))[0]
        else:
            # No idea which variable to generate geometry from... try to factor out axis variables
            var_to_get_geo_from = next(x for x in cd.nc.variables if x not in itertools.chain(_possibley, _possiblex, _possiblez, _possiblet, METADATA_VAR_NAMES))

        messages.append(u"Variable '%s' was used to calculate geometry." % var_to_get_geo_from)

        gj = None
        try:
            gj = mapping(cd.getboundingpolygon(var=var_to_get_geo_from))
        except AttributeError:
            messages.append(u"The underlying 'Paegan' data access library could not determine a bounding POLYGON for this dataset.")
            try:
                # Returns a tuple of four coordinates, but box takes in four seperate positional argouments
                # Asterik magic to expland the tuple into positional arguments
                gj = mapping(box(*cd.getboundingpolygon(var=var_to_get_geo_from)))
            except AttributeError:
                messages.append(u"The underlying 'Paegan' data access library could not determine a bounding BOX for this dataset.")

        service = {
            'name'              : name,
            'description'       : description,
            'service_type'      : self.service.get('service_type'),
            'service_id'        : ObjectId(self.service.get('_id')),
            'data_provider'     : self.service.get('data_provider'),
            'metadata_type'     : u'ncml',
            'metadata_value'    : unicode(dataset2ncml(cd.nc, url=self.service.get('url'))),
            'messages'          : map(unicode, messages),
            'keywords'          : keywords,
            'variables'         : variables,
            'asset_type'        : unicode(cd._datasettype).upper(),
            'geojson'           : gj,
            'updated'           : datetime.utcnow()
        }

        with app.app_context():
            dataset.services.append(service)
            dataset.updated = datetime.utcnow()
            dataset.save()

