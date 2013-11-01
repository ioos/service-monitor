from datetime import datetime
from urlparse import urlparse

import requests
import xml.etree.ElementTree as ET

from owslib import fes, csw
from owslib.util import nspath_eval
from owslib.namespaces import Namespaces

from ioos_catalog import app,db


def reindex_services():
    region_map =    {   'AOOS':         '1706F520-2647-4A33-B7BF-592FAFDE4B45',
                        'CARICOOS':     '117F1684-A5E3-400E-98D8-A270BDBA1603',
                        'CENCOOS':      '4BA5624D-A61F-4C7E-BAEE-7F8BDDB8D9C4',
                        'GCOOS':        '003747E7-4818-43CD-937D-44D5B8E2F4E9',
                        'GLOS':         'B664427E-6953-4517-A874-78DDBBD3893E',
                        'MARACOOS':     'C664F631-6E53-4108-B8DD-EFADF558E408',
                        'NANOOS':       '254CCFC0-E408-4E13-BD62-87567E7586BB',
                        'NERACOOS':     'E41F4FCD-0297-415D-AC53-967B970C3A3E',
                        'PacIOOS':      '68FF11D8-D66B-45EE-B33A-21919BB26421',
                        'SCCOOS':       'B70B3E3C-3851-4BA9-8E9B-C9F195DCEAC7',
                        'SECOORA':      'B3EA8869-B726-4E39-898A-299E53ABBC98' }
                        #'NOS/CO-OPS':   '72E748DF-23B1-4E80-A2C4-81E70783094A',
                        #'USACE':        '73019DFF-2E01-4800-91CD-0B3F812256A7',
                        #'NAVY':         '3B94DAAE-B7E9-4789-993B-0045AD9149D9',
                        #'NDBC':         '828981B0-0039-4360-9788-E788FA6B0875',
                        #'USGS/CMGP':    'C6F11F00-C2BD-4AC6-8E2C-013E16F4932E' }

    services =      {   'SOS'       :   'urn:x-esri:specification:ServiceType:sos:url',
                        'WMS'       :   'urn:x-esri:specification:ServiceType:wms:url',
                        'WCS'       :   'urn:x-esri:specification:ServiceType:wcs:url',
                        'DAP'       :   'urn:x-esri:specification:ServiceType:odp:url' }

    endpoint = 'http://www.ngdc.noaa.gov/geoportal/csw' # NGDC Geoportal

    c = csw.CatalogueServiceWeb(endpoint, timeout=120)

    ns = Namespaces()

    with app.app_context():
        for region,uuid in region_map.iteritems():
            # Setup uuid filter
            uuid_filter = fes.PropertyIsEqualTo(propertyname='sys.siteuuid', literal="{%s}" % uuid)

            # Make CSW request
            c.getrecords2([uuid_filter], esn='full', maxrecords=999999)

            for name, record in c.records.iteritems():

                # @TODO: unfortunately CSW does not provide us with contact info, so
                # we must request it manually
                contact_email = ""
                metadata_url = None

                iso_ref = [x['url'] for x in record.references if x['scheme'] == 'urn:x-esri:specification:ServiceType:ArcIMS:Metadata:Document']
                if len(iso_ref):
                    metadata_url = iso_ref[0]

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

                    # We are only interested in the 'services'
                    if ref["scheme"] in services.values():
                        url = unicode(ref["url"])
                        s =   db.Service.find_one({ 'data_provider' : unicode(region), 'url' : url })
                        if s is None:
                            s               = db.Service()
                            s.url           = url
                            s.data_provider = unicode(region)

                        s.service_id        = unicode(name)
                        s.name              = unicode(record.title)
                        s.service_type      = unicode(next((k for k,v in services.items() if v == ref["scheme"])))
                        s.interval          = 3600 # 1 hour
                        s.tld               = unicode(urlparse(url).netloc)
                        s.updated           = datetime.utcnow()
                        s.contact           = unicode(contact_email)
                        s.metadata_url      = unicode(metadata_url)
                        s.save()
                        s.schedule_harvest()
