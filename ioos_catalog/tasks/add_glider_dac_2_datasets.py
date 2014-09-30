from ioos_catalog import db
import csv
from urlparse import urlparse
try:
    from urllib.request import urlopen
except ImportError:
    from urllib import urlopen
from datetime import datetime


def add_glider_dac_2_datasets():
    url = 'http://erddap.marine.rutgers.edu/erddap/info/index.tsv'

    response = urlopen(url)
    tsv = csv.reader(response, delimiter='\t')
    headers = [(n, val) for (n, val) in enumerate(tsv.next())
               if val in ['Title', 'tabledap', 'ISO 19115', 'Dataset ID']]
    for row in tsv:
        data_dict = {}
        for n, col in headers:
            data_dict[col] = row[n]

        # skip "all" datasets for now
        if data_dict['Dataset ID'] in set(['allDatasets', 'allRutgersGliders']):
            continue
        else:
            now = datetime.utcnow()
            existing_service = db.Service.find_one({'url':
                                                    unicode(data_dict['tabledap'])})
            if existing_service:
                existing_service['updated'] = now
                existing_service['data_provider'] = u'Glider_DAC_2'
                existing_service.save()
                print("Updated '%s'" % existing_service['service_id'])
            else:
                serv = db.Service({'url': unicode(data_dict['tabledap']),
                                'service_id': unicode(data_dict['Dataset ID']),
                                'service_type': u'DAP',
                                'data_provider': u'Glider_DAC_2',
                                'name': unicode(data_dict['Title']),
                                'tld': unicode(urlparse(data_dict['tabledap']).netloc),
                                'metadata_url': (unicode(data_dict['ISO 19115'])
                                                 if data_dict['ISO 19115']
                                                 is not None else None),
                                'updated': now,
                                'manual': True,
                                'active': True,
                                'contact': u"",
                                'interval': 3600
                                })
                serv.save()
                print("Added service '%s'" % serv['service_id'])
