from datetime import datetime
from urlparse import urlparse
import ckanapi

import requests

import re
from owslib.iso import MD_Metadata
from lxml import etree

from ioos_catalog import app,db

ckan_endpoint = ckanapi.RemoteCKAN('http://data.ioos.us/')
region_map = ckan_endpoint.action.organization_list()


services = {'SOS': "OGC:SOS",
            'WCS': "OGC:WCS",
            'WMS': "OGC:WMS",
            'DAP': "OPeNDAP:OPeNDAP"}

def reindex_services(filter_regions=None, filter_service_types=None):


    with app.app_context():

        new_services    = []
        update_services = []

        # get a set of all non-manual, active services for possible deactivation later
        if 'Service' in db.collection_names():
            current_services = set((s._id for s in db.Service.find({'manual':False, 'active':True,
                                                    'data_provider':{'$in':filter_regions}}, {'_id':True})))
        else:
            current_services = set()

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

        for region in region_map:
            records = ckan_endpoint.action.package_search(q='organization:{}'.format(
                                                                       region))['results']
            app.logger.info("Requesting region %s", region)

            for record in records:
                try:
                    # @TODO: unfortunately CSW does not provide us with contact info, so
                    # we must request it manually
                    contact_email = ""
                    metadata_url = None

                    for ref in record['resources']:
                        try:
                            # TODO: Use a more robust mechanism for detecting
                            # ERDDAP instances aside from relying on the url
                            erddap_match = erddap_re.search(ref['url'])
                            # We are only interested in the 'services'
                            if (ref["resource_locator_protocol"] in services.values()):
                                metadata_url = ref['url']
                                # strip extension if erddap endpoint
                                url = unicode(ref['url'])
                            elif erddap_match:
                                test_url = (erddap_match.group(1) +
                                                '.iso19115')
                                req = requests.get(test_url)
                                # if we have a valid ERDDAP metadata endpoint,
                                # store it.
                                if req.status_code == 200:
                                    metadata_url = unicode(test_url)
                                else:
                                    app.logger.error('Invalid service URL %s', ref['url'])
                                    continue

                                url = get_erddap_url_from_iso(req.content)
                                if url is None:
                                    app.logger.error(ref['url'])
                                    app.logger.error("Failed to parse Erddap ISO for %s", test_url)
                                    continue # Either not a valid ISO or there's not a valid endpoint

                            # next record if not one of the previously mentioned
                            else:
                                continue
                            # end metadata find block
                            s = db.Service.find_one({'data_provider':
                                                        unicode(region),
                                                        'url': url})
                            if s is None:
                                s               = db.Service()
                                s.url           = unicode(url)
                                s.data_provider = unicode(region)
                                s.manual        = False
                                s.active        = True

                                new_services.append(s)
                            else:
                                # will run twice if erddap services have
                                # both .html and .graph, but resultant
                                # data should be the same
                                update_services.append(s)

                            #s.service_id   = unicode(name)
                            s.name         = unicode(record['title'])
                            s.service_type = unicode('DAP' if erddap_match
                                                        else next((k for k,v in services.items() if v == ref["resource_locator_protocol"])))
                            s.interval     = 3600 # 1 hour
                            s.tld          = unicode(urlparse(url).netloc)
                            s.updated      = datetime.utcnow()
                            s.contact      = unicode(contact_email)
                            s.metadata_url = metadata_url

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

def get_erddap_url_from_iso(xml_doc):
    griddap_key = 'ERDDAPgriddapDatasetQueryAndAccess'
    opendap_key = 'OPeNDAPDatasetQueryAndAccess'
    tabledap_key = 'ERDDAPtabledapDatasetQueryAndAccess'
    try:
        tree = etree.fromstring(xml_doc)
        metadata = MD_Metadata(tree)
        for ident in metadata.identificationinfo:
            if ident.identtype != 'service':
                continue
            operations = {k['name'] : k for k in ident.operations}
            for key in [opendap_key, griddap_key, tabledap_key]:
                if key in operations:
                    return operations[key]['connectpoint'][0].url
    except Exception as e:
        app.logger.exception('Failed to parse ERDDAP ISO record for griddap')
        return None
