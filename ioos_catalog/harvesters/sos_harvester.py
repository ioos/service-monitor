#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
ioos_catalog/harvesters/sos_harvester.py

Harvester for SOS
'''
from ioos_catalog.harvesters.harvester import Harvester
from ioos_catalog.harvesters import unicode_or_none, get_common_name
from ioos_catalog import app, db

from compliance_checker.runner import ComplianceCheckerCheckSuite
from compliance_checker.ioos import IOOSSOSGCCheck, IOOSSOSDSCheck
from compliance_checker.base import get_namespaces
from wicken.xml_dogma import MultipleXmlDogma

from bson import ObjectId
from datetime import datetime
from lxml import etree

from owslib import ows
from owslib.sos import SensorObservationService
from owslib.swe.sensor.sml import SensorML
from owslib.util import testXMLAttribute
from owslib.crs import Crs

from pyoos.parsers.ioos.describe_sensor import IoosDescribeSensor
from petulantbear import netcdf2ncml

import geojson
import json


class SosHarvester(Harvester):

    def __init__(self, service):
        Harvester.__init__(self, service)

    def _handle_ows_exception(self, **kwargs):
        try:
            return self.sos.describe_sensor(**kwargs)
        except ows.ExceptionReport as e:
            if e.code == 'InvalidParameterValue':
                # TODO: use SOS getCaps to determine valid formats
                # some only work with plain SensorML as the format

                # see if O&M will work instead
                try:
                    kwargs[
                        'outputFormat'] = 'text/xml;subtype="om/1.0.0/profiles/ioos_sos/1.0"'
                    return self.sos.describe_sensor(**kwargs)

                # see if plain sensorml wll work
                except ows.ExceptionReport as e:
                    # if this fails, just raise the exception without handling
                    # here
                    kwargs['outputFormat'] = 'text/xml;subtype="sensorML/1.0.1"'
                    return self.sos.describe_sensor(**kwargs)
            elif e.msg == 'No data found for this station':
                raise e

    def _describe_sensor(self, uid, timeout=120,
                         outputFormat='text/xml;subtype="sensorML/1.0.1/profiles/ioos_sos/1.0"'):
        """
        Issues a DescribeSensor request with fallback behavior for oddly-acting SOS servers.
        """
        kwargs = {
            'outputFormat': outputFormat,
            'procedure': uid,
            'timeout': timeout
        }

        return self._handle_ows_exception(**kwargs)

    def harvest(self):
        self.sos = SensorObservationService(self.service.get('url'))

        scores = self.ccheck_service()
        metamap = self.metamap_service()
        try:
            self.save_ccheck_service('ioos', scores, metamap)
        finally:
            pass

        # List storing the stations that have already been processed in this SOS server.
        # This is kept and checked later to avoid servers that have the same
        # stations in many offerings.
        processed = []

        # handle network:all by increasing max timeout
        net_len = len(self.sos.offerings)
        net_timeout = 120 if net_len <= 36 else 5 * net_len

        # allow searching child offerings for by name for network offerings
        name_lookup = {o.name: o for o in self.sos.offerings}
        for offering in self.sos.offerings:
            # TODO: We assume an offering should only have one procedure here
            # which will be the case in sos 2.0, but may not be the case right now
            # on some non IOOS supported servers.
            uid = offering.procedures[0]
            sp_uid = uid.split(":")

            # template:   urn:ioos:type:authority:id
            # sample:     ioos:station:wmo:21414
            if len(sp_uid) > 2 and sp_uid[2] == "network":  # Network Offering
                if uid[-3:].lower() == 'all':
                    continue  # Skip the all
                net = self._describe_sensor(uid, timeout=net_timeout)

                network_ds = IoosDescribeSensor(net)
                # Iterate over stations in the network and process them
                # individually

                for proc in network_ds.procedures:

                    if proc is not None and proc.split(":")[2] == "station":
                        if proc not in processed:
                            # offering associated with this procedure
                            proc_off = name_lookup.get(proc)
                            self.process_station(proc, proc_off)
                        processed.append(proc)
            else:
                # Station Offering, or malformed urn - try it anyway as if it
                # is a station
                if uid not in processed:
                    self.process_station(uid, offering)
                processed.append(uid)

    def process_station(self, uid, offering):
        """ Makes a DescribeSensor request based on a 'uid' parameter being a
            station procedure.  Also pass along an offering with
            getCapabilities information for items such as temporal extent"""

        GML_NS = "http://www.opengis.net/gml"

        with app.app_context():

            app.logger.info("process_station: %s", uid)
            desc_sens = self._describe_sensor(uid, timeout=1200)
            # FIXME: add some kind of notice saying the station failed
            if desc_sens is None:
                app.logger.warn(
                    "Could not get a valid describeSensor response")
                return
            metadata_value = etree.fromstring(desc_sens)
            sensor_ml = SensorML(metadata_value)
            try:
                station_ds = IoosDescribeSensor(metadata_value)
            # if this doesn't conform to IOOS SensorML sub, fall back to
            # manually picking apart the SensorML
            except ows.ExceptionReport:
                station_ds = netcdf2ncml.process_sensorml(sensor_ml.members[0])

            unique_id = station_ds.id
            if unique_id is None:
                app.logger.warn(
                    "Could not get a 'stationID' from the SensorML "
                    "identifiers.  Looking for a definition of "
                    "'http://mmisw.org/ont/ioos/definition/stationID'")
                return

            dataset = db.Dataset.find_one({'uid': unicode(unique_id)})
            if dataset is None:
                dataset = db.Dataset()
                dataset.uid = unicode(unique_id)
                dataset['active'] = True

            # Find service reference in Dataset.services and remove (to replace
            # it)
            tmp = dataset.services[:]
            for d in tmp:
                if d['service_id'] == self.service.get('_id'):
                    dataset.services.remove(d)

            # Parsing messages
            messages = []

            # NAME
            name = unicode_or_none(station_ds.shortName)
            if name is None:
                messages.append(
                    u"Could not get a 'shortName' from the SensorML "
                    u"identifiers.  Looking for a definition of "
                    u"'http://mmisw.org/ont/ioos/definition/shortName'")

            # DESCRIPTION
            description = unicode_or_none(station_ds.longName)
            if description is None:
                messages.append(
                    u"Could not get a 'longName' from the SensorML "
                    u"identifiers.  Looking for a definition of "
                    u"'http://mmisw.org/ont/ioos/definition/longName'")

            # PLATFORM TYPE
            asset_type = unicode_or_none(getattr(station_ds,
                                                 'platformType', None))
            if asset_type is None:
                messages.append(
                    u"Could not get a 'platformType' from the SensorML "
                    u"identifiers.  Looking for a definition of "
                    u"'http://mmisw.org/ont/ioos/definition/platformType'")

            # LOCATION is in GML
            gj = None
            loc = station_ds.location
            if loc is not None and loc.tag == "{%s}Point" % GML_NS:
                pos_element = loc.find("{%s}pos" % GML_NS)
                # some older responses may uses the deprecated coordinates
                # element
                if pos_element is None:
                    # if pos not found use deprecated coordinates element
                    pos_element = loc.find("{%s}coordinates" % GML_NS)
                # strip out points
                positions = map(float, pos_element.text.split(" "))

                for el in [pos_element, loc]:
                    srs_name = testXMLAttribute(el, "srsName")
                    if srs_name:
                        crs = Crs(srs_name)
                        if crs.axisorder == "yx":
                            gj = json.loads(geojson.dumps(
                                geojson.Point([positions[1], positions[0]])))
                        else:
                            gj = json.loads(geojson.dumps(
                                geojson.Point([positions[0], positions[1]])))
                        break
                else:
                    if positions:
                        messages.append(
                            u"Position(s) found but could not parse SRS: %s, %s" % (positions, srs_name))

            else:
                messages.append(
                    u"Found an unrecognized child of the sml:location element and did not attempt to process it: %s" % loc)

            meta_str = unicode(etree.tostring(metadata_value)).strip()
            if len(meta_str) > 4000000:
                messages.append(
                    u'Metadata document was too large to store (len: %s)' % len(meta_str))
                meta_str = u''

            service = {
                # Reset service
                'name': name,
                'description': description,
                'service_type': self.service.get('service_type'),
                'service_id': ObjectId(self.service.get('_id')),
                'data_provider': self.service.get('data_provider'),
                'metadata_type': u'sensorml',
                'metadata_value': u'',
                'time_min': getattr(offering, 'begin_position', None),
                'time_max': getattr(offering, 'end_position', None),
                'messages': map(unicode, messages),
                'keywords': map(unicode, sorted(station_ds.keywords)),
                'variables': map(unicode, sorted(station_ds.variables)),
                'asset_type': get_common_name(asset_type),
                'geojson': gj,
                'updated': datetime.utcnow()
            }

            dataset.services.append(service)
            dataset.updated = datetime.utcnow()
            dataset.save()

            # do compliance checker / metadata now
            scores = self.ccheck_station(sensor_ml)
            metamap = self.metamap_station(sensor_ml)

            try:
                self.save_ccheck_station('ioos', dataset._id, scores, metamap)
            except Exception as e:
                app.logger.warn(
                    "could not save compliancecheck/metamap information: %s", e)

            return "Harvest Successful"

    def ccheck_service(self):
        assert self.sos

        with app.app_context():

            scores = None

            try:
                cs = ComplianceCheckerCheckSuite()
                groups = cs.run(self.sos, 'ioos')
                scores = groups['ioos']
            except Exception as e:
                app.logger.warn(
                    "Caught exception doing Compliance Checker on SOS service: %s", e)

            return scores

    def metamap_service(self):
        assert self.sos

        with app.app_context():
            # gets a metamap document of this service using wicken
            beliefs = IOOSSOSGCCheck.beliefs()
            doc = MultipleXmlDogma(
                'sos-gc', beliefs, self.sos._capabilities, namespaces=get_namespaces())

            # now make a map out of this
            # @TODO wicken should make this easier
            metamap = {}
            for k in beliefs:
                try:
                    metamap[k] = getattr(doc, doc._fixup_belief(k)[0])
                except Exception:
                    pass

            return metamap

    def save_ccheck_service(self, checker_name, scores, metamap):
        """
        Saves the result of ccheck_service and metamap
        """
        return self.save_ccheck_and_metadata(self.service._id,
                                             checker_name,
                                             self.service._id,
                                             u'service',
                                             scores,
                                             metamap)

    def ccheck_station(self, sensor_ml):
        with app.app_context():
            scores = None
            try:
                cs = ComplianceCheckerCheckSuite()
                groups = cs.run(sensor_ml, 'ioos')
                scores = groups['ioos']
            except Exception as e:
                app.logger.warn(
                    "Caught exception doing Compliance Checker on SOS station: %s", e)

            return scores

    def metamap_station(self, sensor_ml):
        with app.app_context():
            # gets a metamap document of this service using wicken
            beliefs = IOOSSOSDSCheck.beliefs()
            doc = MultipleXmlDogma(
                'sos-ds', beliefs, sensor_ml._root, namespaces=get_namespaces())

            # now make a map out of this
            # @TODO wicken should make this easier
            metamap = {}
            for k in beliefs:
                try:
                    metamap[k] = getattr(doc, doc._fixup_belief(k)[0])
                except:
                    pass

            return metamap

    def save_ccheck_station(self, checker_name, dataset_id, scores, metamap):
        """
        Saves the result of ccheck_station and metamap
        """
        return self.save_ccheck_and_metadata(self.service._id,
                                             checker_name,
                                             dataset_id,
                                             u'dataset',
                                             scores,
                                             metamap)
