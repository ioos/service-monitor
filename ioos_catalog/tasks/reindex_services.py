from datetime import datetime
from urlparse import urlparse
import re

import requests
import xml.etree.ElementTree as ET

from owslib import fes, csw
from owslib.util import nspath_eval
from owslib.namespaces import Namespaces

from ioos_catalog import app,db
import requests

region_map =    {'AOOS'             : '1706F520-2647-4A33-B7BF-592FAFDE4B45',
                 'ATN_DAC'          : '07875897-E6A6-4EDB-B111-F5D6BE841ED6',
                 'CARICOOS'         : '117F1684-A5E3-400E-98D8-A270BDBA1603',
                 'CDIP'             : '4EA30508-7E2B-474E-BFD2-9B482E8DE9B6',
                 'CeNCOOS'          : '4BA5624D-A61F-4C7E-BAEE-7F8BDDB8D9C4',
                 'GCOOS'            : '003747E7-4818-43CD-937D-44D5B8E2F4E9',
                 'Glider_DAC'       : '2546E50F-F0C7-4365-9D45-694DD22E5F26',
                 'GLOS'             : 'B664427E-6953-4517-A874-78DDBBD3893E',
                 'HFradar_DAC'      : 'A4A65346-6B65-4ED2-A2DC-5D529074EE6D',
                 'MARACOOS'         : 'C664F631-6E53-4108-B8DD-EFADF558E408',
                 'MODELING_TESTBED' : '8BF00750-66C7-49FF-8894-4D4F96FD86C0',
                 'NANOOS'           : '254CCFC0-E408-4E13-BD62-87567E7586BB',
                 'NERACOOS'         : 'E41F4FCD-0297-415D-AC53-967B970C3A3E',
                 'PacIOOS'          : '68FF11D8-D66B-45EE-B33A-21919BB26421',
                 'SCCOOS'           : 'B70B3E3C-3851-4BA9-8E9B-C9F195DCEAC7',
                 'SECOORA'          : 'B3EA8869-B726-4E39-898A-299E53ABBC98',
                 'NOAA-CO-OPS'      : '72E748DF-23B1-4E80-A2C4-81E70783094A',
                 'USACE'            : '73019DFF-2E01-4800-91CD-0B3F812256A7',
                 'NAVY'             : '3B94DAAE-B7E9-4789-993B-0045AD9149D9',
                 'NOAA-NDBC'        : '828981B0-0039-4360-9788-E788FA6B0875',
                 'USGS-CMGP'        : 'C6F11F00-C2BD-4AC6-8E2C-013E16F4932E',
                 'Other'            : '7EDF86E1-573C-4B3C-A979-AD499A11FD22'}

services =      {'SOS'              : 'urn:x-esri:specification:ServiceType:sos:url',
                 'WMS'              : 'urn:x-esri:specification:ServiceType:wms:url',
                 'WCS'              : 'urn:x-esri:specification:ServiceType:wcs:url',
                 'DAP'              : 'urn:x-esri:specification:ServiceType:odp:url' }

opendap_form_schema = 'urn:x-esri:specification:ServiceType:distribution:url'       # used to pull additional data from DAP types

endpoint = 'http://www.ngdc.noaa.gov/geoportal/csw' # NGDC Geoportal

def reindex_services(filter_regions=None, filter_service_types=None):
    c = csw.CatalogueServiceWeb(endpoint, timeout=120)

    ns = Namespaces()

    filter_regions = filter_regions or region_map.keys()
    filter_service_types = filter_service_types or services.keys()

    with app.app_context():

        new_services    = []
        update_services = []

        # get a set of all non-manual, active services for possible deactivation later
        current_services = set((s._id for s in db.Service.find({'manual':False, 'active':True, 'data_provider':{'$in':filter_regions}}, {'_id':True})))

        # FIXME: find a more robust mechanism for detecting ERDDAP instances
        # this would fail if behind a url rewriting/proxying mechanism which
        # remove the 'erddap' portion from the URL.  May want to have GeoPortal
        # use a separate 'scheme' dedicated to ERDDAP for CSW record
        # 'references'

        # workaround for matching ERDDAP endpoints
        # match griddap or tabledap endpoints with html or graph
        # discarding any query string parameters (i.e. some datasets on PacIOOS)
        re_string = r'(^.*erddap/(?:grid|table)dap.*)\.(?:html|graph)(:?\?.*)?$'
        erddap_re = re.compile(re_string)
        erddap_all_re = re.compile(r'(^.*erddap/(?:(?:grid|table|)dap|wms).*)'
                                   r'\.(?:html|graph)(:?\?.*)?$')

        for region,uuid in region_map.iteritems():

            if region not in filter_regions:
                app.logger.info("Skipping region %s due to filter", region)
                continue

            app.logger.info("Requesting region %s", region)

            # Setup uuid filter
            uuid_filter = fes.PropertyIsEqualTo(propertyname='sys.siteuuid', literal="{%s}" % uuid)

            # Make CSW request
            c.getrecords2([uuid_filter], esn='full', maxrecords=999999)

            for name, record in c.records.iteritems():

                try:
                    # @TODO: unfortunately CSW does not provide us with contact info, so
                    # we must request it manually
                    contact_email = ""
                    metadata_url = None

                    for r in record.references:
                        if r['scheme'] == 'urn:x-esri:specification:ServiceType:ArcIMS:Metadata:Document':
                            metadata_url = unicode(r['url'])
                            break
                        else:
                            erddap_match = erddap_all_re.search(r['url'])
                            if erddap_match:
                                # test if there is an ISO metadata endpoint
                                test_url = (erddap_match.group(1) +
                                                '.iso19115')
                                req = requests.get(test_url)
                                # if we have a valid ERDDAP metadata endpoint,
                                # store it.
                                if req.status_code == 200:
                                    metadata_url = unicode(test_url)
                                    break

                        # Don't query for contact info right now.  It takes WAY too long.
                        #r = requests.get(iso_ref[0])
                        #r.raise_for_status()
                        #node = ET.fromstring(r.content)
                        #safe = nspath_eval("gmd:CI_ResponsibleParty/gmd:contactInfo/gmd:CI_Contact/gmd:address/gmd:CI_Address/gmd:electronicMailAddress/gco:CharacterString", ns.get_namespaces())
                        #contact_node = node.find(".//" + safe)
                        #if contact_node is not None and contact_node.text != "":
                        #    contact_email = contact_node.text
                        #    if " or " in contact_email:
                        #        contact_email = ",".join(contact_email.split(" or "))

                    for ref in record.references:

                        try:
                            # TODO: Use a more robust mechanism for detecting
                            # ERDDAP instances aside from relying on the url
                            erddap_match = erddap_re.search(ref['url'])
                            # We are only interested in the 'services'
                            if (ref["scheme"] in services.values() or
                               erddap_match):
                                # strip extension if erddap endpoint
                                url = unicode(erddap_match.group(1)
                                              if erddap_match else ref['url'])
                                s = db.Service.find_one({'data_provider':
                                                         unicode(region),
                                                         'url': url})
                                if s is None:
                                    s               = db.Service()
                                    s.url           = url
                                    s.data_provider = unicode(region)
                                    s.manual        = False
                                    s.active        = True

                                    new_services.append(s)
                                else:
                                    # will run twice if erddap services have
                                    # both .html and .graph, but resultant
                                    # data should be the same
                                    update_services.append(s)

                                s.service_id   = unicode(name)
                                s.name         = unicode(record.title)
                                s.service_type = unicode('DAP' if erddap_match
                                                          else next((k for k,v in services.items() if v == ref["scheme"])))
                                s.interval     = 3600 # 1 hour
                                s.tld          = unicode(urlparse(url).netloc)
                                s.updated      = datetime.utcnow()
                                s.contact      = unicode(contact_email)
                                s.metadata_url = metadata_url

                                # grab opendap form url if present
                                if s.service_type == 'DAP':
                                    possible_refs = [r['url'] for r in record.references if r['scheme'] == opendap_form_schema]
                                    if len(possible_refs):
                                        s.extra_url = unicode(possible_refs[0])

                                # if we see the service, this is "Active", unless we've set manual (then we don't touch)
                                if not s.manual:
                                    s.active = True

                                s.save()

                        except Exception as e:
                            app.logger.warn("Could not save service: %s", e)

                except Exception as e:
                    app.logger.warn("Could not save region info: %s", e)

        # DEACTIVATE KNOWN SERVICES
        updated_ids = set((s._id for s in update_services))
        deactivate = list(current_services.difference(updated_ids))

        # bulk update (using pymongo syntax)
        db.services.update({'_id':{'$in':deactivate}},
                           {'$set':{'active':False,
                                    'updated':datetime.utcnow()}},
                           multi=True,
                           upsert=False)

        return "New services: %s, updated services: %s, deactivated services: %s" % (len(new_services), len(update_services), len(deactivate))

def cleanup_datasets():
    with app.app_context():
        datasets = db.Dataset.find({'active':True})
        for d in datasets:
            services = d['services'] # a list of services
            service_ids = [s['service_id'] for s in services]
            if not service_ids:
                app.logger.info('Deactivating %s', d['uid'])
                d['active'] = False
                d.save()
                continue

            # Go through each of the services
            #
            # if we don't find at least one service that is active, set
            # dataset.active to False
            for service_id in service_ids:
                related_services = db.Service.find({'_id':service_id})
                for service in related_services:
                    if service['active']:
                        break
                else: # reached the end of the loop
                    app.logger.info('Deactivating %s', d['uid'])
                    d['active'] = False
                    d.save()
                    break

