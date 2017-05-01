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
from urllib import urlencode
import geojson
import json


IOOS_SENSORML = 'text/xml;subtype="sensorML/1.0.1/profiles/ioos_sos/1.0"'
IOOS_SWE = 'text/xml;subtype="om/1.0.0/profiles/ioos_sos/1.0"'
SENSORML = 'text/xml;subtype="sensorML/1.0.1"'


class SosHarvestError(Exception):
    def __init__(self, message):
        self.message = message
        self.messages = [message]

    def append(self, message):
        self.messages.append(message)

    def __repr__(self):
        return '\n'.join(['SosHarvestError'] + self.messages)


class DescribeSensorError(SosHarvestError):
    pass


class SosFormatError(SosHarvestError):
    pass


class SosHarvester(Harvester):

    def __init__(self, service):
        Harvester.__init__(self, service)
        self.output_format = IOOS_SENSORML

    def _handle_ows_exception(self, **kwargs):
        # Put the current output format first, this will prevent us from trying
        # subsequent calls with different formats.
        formats = [IOOS_SENSORML, IOOS_SWE, SENSORML]
        formats.pop(formats.index(self.output_format))
        formats.insert(0, self.output_format)
        for output_format in formats:
            try:
                self.output_format = output_format
                kwargs['outputFormat'] = output_format
                return self.sos.describe_sensor(**kwargs)
            except ows.ExceptionReport as e:
                if e.code == 'InvalidParameterValue':
                    continue
                e.msg = e.msg + '\n' + self.format_url(kwargs['procedure'])
                raise e
        else:

            raise SosFormatError('No valid outputFormat found for DescribeSensor\n' +
                                 self.service.url)

    def _describe_sensor(self, uid, timeout=120):
        """
        Issues a DescribeSensor request with fallback behavior for oddly-acting SOS servers.
        """
        kwargs = {
            'procedure': uid,
            'timeout': timeout
        }

        return self._handle_ows_exception(**kwargs)

    def format_url(self, procedure, outputFormat=None):
        '''
        Returns the full SOS GET URL for the offering/procedure.
        '''
        if outputFormat is None:
            outputFormat = self.output_format
        try:
            base_url = next((m.get('url') for m in self.sos.getOperationByName('DescribeSensor').methods if m.get('type').lower() == 'get'))
        except StopIteration:
            base_url = self.sos.url

        while base_url.endswith('?'):
            base_url = base_url[:-1]

        request = {'service': 'SOS', 'version': self.sos.version, 'request': 'DescribeSensor'}
        if isinstance(outputFormat, str):
            request['outputFormat'] = outputFormat
        if isinstance(procedure, str):
            request['procedure'] = procedure
        data = urlencode(request)
        url = base_url + '?' + data
        return url

    def update_service_metadata(self):
        metamap = self.metamap_service()
        metadata = db.Metadata.find_one({"ref_id": self.service._id})
        if metadata is None:
            metadata = db.Metadata()
            metadata.ref_id = self.service._id
            metadata.ref_type = u'service'

        update = {
            'cc_score': {
                'score': 0.,
                'max_score': 0.,
                'pct': 0.
            },
            'cc_results': [],
            'metamap': metamap
        }
        for record in metadata.metadata:
            if record['service_id'] == self.service._id:
                record.update(update)
                break
        else:
            record = {
                'service_id': self.service._id,
                'checker': None
            }
            record.update(update)
            metadata.metadata.append(record)

        metadata.updated = datetime.utcnow()
        metadata.save()
        return metadata

    def update_dataset_metadata(self, dataset_id, sensor_ml, describe_sensor_url=None):
        metamap = self.metamap_station(sensor_ml)
        if describe_sensor_url:
            metamap['Describe Sensor URL'] = describe_sensor_url
        metadata = db.Metadata.find_one({"ref_id": dataset_id})
        if metadata is None:
            metadata = db.Metadata()
            metadata.ref_id = dataset_id
            metadata.ref_type = u'dataset'

        update = {
            'cc_score': {
                'score': 0.,
                'max_score': 0.,
                'pct': 0.
            },
            'cc_results': [],
            'metamap': metamap
        }
        for record in metadata.metadata:
            if record['service_id'] == self.service._id:
                record.update(update)
                break
        else:
            record = {
                'service_id': self.service._id,
                'checker': None
            }
            record.update(update)
            metadata.metadata.append(record)

        metadata.updated = datetime.utcnow()
        metadata.save()
        return metadata

    def harvest(self):
        self.sos = SensorObservationService(self.service.get('url'))

        self.update_service_metadata()

        # List storing the stations that have already been processed in this SOS server.
        # This is kept and checked later to avoid servers that have the same
        # stations in many offerings.
        processed = []

        exception = None

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
                try:
                    net = self._describe_sensor(uid, timeout=net_timeout)
                except Exception as e:
                    message = '\n'.join(['DescribeSensor failed for {}'.format(uid), e.message])
                    if exception is None:
                        exception = DescribeSensorError(message)
                    else:
                        exception.append(message)

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
                    try:
                        self.process_station(uid, offering)
                    except SosHarvestError as e:
                        message = '\n'.join(['DescribeSensor failed for {}'.format(uid), e.message])
                        if exception is None:
                            exception = e
                        exception.append(message)
                    except Exception as e:
                        message = '\n'.join(['DescribeSensor failed for {}'.format(uid), e.message])
                        if exception is None:
                            exception = DescribeSensorError(message)
                        else:
                            exception.append(message)

                processed.append(uid)

            if exception is not None:
                raise exception

    def process_station(self, uid, offering):
        """ Makes a DescribeSensor request based on a 'uid' parameter being a
            station procedure.  Also pass along an offering with
            getCapabilities information for items such as temporal extent"""

        GML_NS = "http://www.opengis.net/gml"

        with app.app_context():

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
            dataset_services = dataset.services[:]
            for service in dataset_services:
                if service['url'] == self.service.get('url'):
                    dataset.services.remove(service)

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
                'url': self.service.url,
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
            dataset.service_url = self.service.url

            dataset.services.append(service)
            dataset.updated = datetime.utcnow()
            dataset.save()

            # do compliance checker / metadata now

            try:
                describe_sensor_url = self.format_url(uid)
                self.update_dataset_metadata(dataset._id, sensor_ml, describe_sensor_url)
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
