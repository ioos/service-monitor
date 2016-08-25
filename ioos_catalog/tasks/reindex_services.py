#!/usr/bin/env python
'''
ioos_catalog/tasks/reindex_services.py
'''
from urlparse import urlparse
from collections import namedtuple
from hashlib import sha1
from owslib.iso import MD_Metadata
from lxml import etree
from ioos_catalog import app, db
from datetime import datetime, timedelta

import ckanapi
import requests
import re

PROTOCOLS = {
    u"OGC:SOS": u"SOS",
    u"OGC:WCS": u"WCS",
    u"OGC:WMS": u"WMS",
    u"OPeNDAP:OPeNDAP": u"DAP"
}

URLPair = namedtuple('URLPair', ['url', 'metadata_url'])

# Compiled regexes
re_string = r'(^.*erddap/(?:grid|table)dap.*)\.(?:html|graph)(:?\?.*)?$'
erddap_re = re.compile(re_string)
erddap_all_re = re.compile(r'(^.*erddap/(?:(?:grid|table|)dap|wms).*)'
                           r'\.(?:html|graph)(:?\?.*)?$')


def fetch_records(organization_id):
    '''
    Repeatedly fetches records from the CKAN API until all are fetched for a
    given organization

    :param str organization_id: CKAN Org ID
    '''

    records = []
    offset = 0
    ckan_endpoint = ckanapi.RemoteCKAN(app.config['CKAN_CATALOG'])
    initial_set = ckan_endpoint.action.package_search(q='organization:{}'.format(organization_id), rows=100)
    count = initial_set['count']
    records.extend(initial_set['results'])
    offset += len(initial_set['results'])
    while len(records) < count:
        record_set = ckan_endpoint.action.package_search(q='organization:{}'.format(organization_id), rows=100, start=offset)
        records.extend(record_set['results'])
        offset += len(record_set['results'])
    return records


def get_region_map():
    ckan_endpoint = ckanapi.RemoteCKAN(app.config['CKAN_CATALOG'])
    region_map = ckan_endpoint.action.organization_list(all_fields=True)
    return region_map


def reindex_services(provider=None):
    '''
    Downloads all records from CKAN and creates service records for the
    appropriate resources defined in those records.
    '''
    region_map = get_region_map()
    if provider is not None:
        region_map = [org for org in region_map if org['name'] == provider]

    with app.app_context():

        for organization in region_map:
            index_organization(organization)

        # Deactivate any service older than 7 days
        old = datetime.utcnow() - timedelta(days=7)
        db.services.update({"updated": {"$lt": old}},
                           {"$set": {"active": False, "updated": datetime.utcnow()}},
                           multi=True,
                           upsert=False)

        return


def index_organization(organization):
    '''
    Downloads all the records for a given organization and creates records for
    the services.

    :param dict organization: Organization record from CKAN
    '''
    records = fetch_records(organization['name'])
    app.logger.info("Requesting region %s", organization['name'])

    for record in records:
        try:
            for service in record['resources']:
                try:

                    index_service(record, organization, service)
                except Exception as e:
                    app.logger.warn("Could not save service: %s", e)

        except Exception as e:
            app.logger.warn("Could not save region info: %s", e)


def get_urls(service):
    '''
    Returns a namedtuple of url and metadata url for the service if it's a valid
    service. Returns None otherwise.

    :param dict service: Dictionary containing service information
    '''
    # ERDDAP instances aside from relying on the url
    erddap_match = erddap_re.search(service['url'])
    # We are only interested in the 'services'
    if service["resource_locator_protocol"] in PROTOCOLS:
        metadata_url = service['url']
        # strip extension if erddap endpoint
        url = unicode(service['url'])
    elif erddap_match:
        test_url = erddap_match.group(1) + '.iso19115'
        req = requests.get(test_url)
        # if we have a valid ERDDAP metadata endpoint,
        # store it.
        if req.status_code == 200:
            metadata_url = unicode(test_url)
        else:
            app.logger.error('Invalid service URL %s', service['url'])
            return

        url = get_erddap_url_from_iso(req.content)
        if url is None:
            app.logger.error(service['url'])
            app.logger.error("Failed to parse Erddap ISO for %s", test_url)
            return

    else:
        # This doesn't contain any valid services, so, continue.
        return
    return URLPair(url, metadata_url)


def index_service(record, organization, service):
    '''
    Indexes a service record into the MongoDB with the provided CKAN metadata
    record.  Returns True if a new service was created.

    :param dict record: Record from CKAN
    :param dict organization: Organization with all fields from CKAN
    :param dict service: A dictionary describing a resource within a record from CKAN
    :rtype: bool
    :return: True if a new service record was created
    '''
    urls = get_urls(service)
    extras = {x['key']: x['value'] for x in record['extras']}
    service_created = False
    if urls is None:
        return

    erddap_match = erddap_re.search(service['url'])

    s = db.Service.find_one({
        'data_provider': unicode(organization['title']),
        'url': urls.url
    })

    if s is None:
        s = db.Service()
        s.url = unicode(urls.url)
        s.data_provider = unicode(organization['title'])
        s.manual = False
        s.active = True

        service_created = True

    # Set service_id = GUID in the extras key, value array
    s.service_id = unicode(sha1(urls.url).hexdigest())
    s.name = unicode(record['title'])
    if erddap_match:
        s.service_type = u'DAP'
    else:
        s.service_type = PROTOCOLS[service['resource_locator_protocol']]
    s.interval = 3600  # 1 hour
    s.tld = unicode(urlparse(urls.url).netloc)
    s.updated = datetime.utcnow()
    s.contact = extras.get('contact-email', '')
    s.metadata_url = urls.metadata_url

    # if we see the service, this is "Active", unless we've set manual (then we don't touch)
    if not s.manual:
        s.active = True

    s.save()
    return service_created


def cleanup_datasets():
    '''
    Cleans up services
    '''
    with app.app_context():
        datasets = db.Dataset.find({'active': True})
        for d in datasets:
            services = d['services']  # a list of services
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
                related_services = db.Service.find({'_id': service_id})
                for service in related_services:
                    if service['active']:
                        break
                else:  # reached the end of the loop
                    app.logger.info('Deactivating %s', d['uid'])
                    d['active'] = False
                    d.save()
                    break


def get_erddap_url_from_iso(xml_doc):
    '''
    Gets a valid URL from a given ERDDAP endpoint
    '''
    griddap_key = 'ERDDAPgriddapDatasetQueryAndAccess'
    opendap_key = 'OPeNDAPDatasetQueryAndAccess'
    tabledap_key = 'ERDDAPtabledapDatasetQueryAndAccess'
    try:
        tree = etree.fromstring(xml_doc)
        metadata = MD_Metadata(tree)
        for ident in metadata.identificationinfo:
            if ident.identtype != 'service':
                continue
            operations = {k['name']: k for k in ident.operations}
            for key in [opendap_key, griddap_key, tabledap_key]:
                if key in operations:
                    return operations[key]['connectpoint'][0].url
    except:
        app.logger.exception('Failed to parse ERDDAP ISO record for griddap')
        return None
