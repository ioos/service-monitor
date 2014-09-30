from flask import render_template, redirect, url_for, request, flash, jsonify, Response, g
from ioos_catalog import app, db
from ioos_catalog.tasks.reindex_services import region_map

# additional information about providers
# please PR/extend!

#Consider using this as a db model fixture for the database instead
#of using a raw dict to populate the information about RAs
#or consolidate region_map's provider UIDs
provider_info = {
    'AOOS': {
        'fullname': 'Alaska Ocean Observing System',
        'provider_type': 'regional',
        'links': [
            {'title':'AOOS Site', 'url': 'http://www.aoos.org'},
            {'title':'AOOS Ocean Data Explorer', 'url':'http://portal.aoos.org/alaska-statewide.php'}
        ]
    },
    'ATN_DAC': {
        'provider_type': 'national',
    },
    'CARICOOS': {
        'fullname': 'Carribean Coastal Ocean Observing System',
        'provider_type': 'regional',
        'description': 'CarICOOS is the observing arm of the Caribbean Regional Association for Integrated Coastal Ocean Observing (CaRA) http://cara.uprm.edu/. This effort, funded by the NOAA IOOS office http://ioos.noaa.gov/, is one of eleven coastal observing systems and regional associations which along with federal agencies constitute the national coastal component of the US Integrated Ocean Observing System.',
        'links': [
            {'title':'CariCOOS Site', 'url': 'http://www.caricoos.org'},
        ]
    },
    'CENCOOS': {
        'fullname': 'The Central and Northern California Ocean Observing System',
        'provider_type': 'regional',
        'banner': '/static/img/ra/cencoos.jpg',
        'description': 'The Central and Northern California Ocean Observing System (CeNCOOS) is one of eleven regional associations within the Integrated Ocean Observing System (IOOS) around the nation dedicated to the support of science in the service of marine ecosystem health and resource sustainability.',
        'links': [
            {'title':'CeNCOOS Site', 'url': 'http://www.cencoos.org'},
            {'title':'CeNCOOS Data Portal', 'url': 'http://data.cencoos.org'},
        ],
    },
    'CDIP': {
        'fullname': 'Coastal Data Information Program',
        'provider_type': 'national',
        'banner': '/static/img/np/cdip.png',
        'description': 'The Coastal Data Information Program (CDIP) measures, analyzes, archives, and disseminates coastal environment data for use by coastal engineers, planners, and managers as well as scientists and mariners.',
        'links': [
            {'title':'CDIP Site', 'url': 'http://cdip.ucsd.edu/'}
        ],
    },
    'GCOOS': {
        'fullname': 'Gulf of Mexico Ocean Observing System',
        'provider_type': 'regional',
        'banner': '/static/img/ra/gcoos.jpg',
        'description': 'The Gulf of Mexico Coastal Ocean Observing System (GCOOS) provides timely information about the environment of the United States portion of the Gulf of Mexico and its estuaries for use by decision-makers, including researchers, government managers, industry, the military, educators, emergency responders, and the general public.',
        'links': [
            {'title':'GCOOS Site', 'url': 'http://gcoos.tamu.edu'},
            {'title':'GCOOS Data Portal', 'url': 'http://data.gcoos.org/'},
        ],
    },
    'Glider_DAC': {
        'fullname': 'IOOS Glider DAC',
        'provider_type': 'national',
        'banner': '/static/img/ioos.png',
        'description': 'IOOS Glider Data Assembly Center',
        'links': [
            {'title': 'Glider DAC', 'url': 'http://gliders.ioos.us/'},
            {'title': 'Glider DAC TDS Catalog', 'url': 'http://tds.gliders.ioos.us/thredds/catalog.html'},
        ]
    },
    'GLOS': {
        'fullname': 'Great Lakes Observing System',
        'provider_type': 'regional',
        'banner': '/static/img/ra/glos.jpg',
        'description': 'GLOS is one of 11 Regional Associations of the Integrated Ocean Observing System (IOOS), working to enhance the ability to collect, deliver, and use ocean and Great Lakes information. IOOS is a partnership among federal, regional, academic and private sector parties that works to provide new tools and forecasts to improve safety, enhance the economy, and protect our environment.',
        'links': [
            {'title':'GLOS Site', 'url': 'http://www.glos.us'},
            {'title':'GLOS Data Portal', 'url':'http://data.glos.us/portal'}
        ]
    },
    'HFradar_DAC': {
        'fullname': 'IOOS High Frequency Radar DAC',
        'provider_type': 'national',
        'banner': '/static/img/ioos.png',
        'description': 'IOOS High Frequency Radar DAC',
        'links': [
            {'title': 'IOOS HF Radar Site', 'url': 'http://www.ioos.noaa.gov/hfradar/welcome.html'}
        ]
    },
    'MARACOOS': {
        'fullname': 'Mid-Atlantic Regional Association Coastal Ocean Observing System',
        'provider_type': 'regional',
        'banner': '/static/img/ra/maracoos.png',
        'description': 'MARACOOS is the Mid-Atlantic Regional Association Coastal Ocean Observing System, covering the region from Cape Cod, MA to Cape Hatteras, NC for U.S. IOOS.',
        'links': [
            {'title':'MARACOOS Site', 'url': 'http://www.maracoos.org'},
            {'title':'MARACOOS Asset Map', 'url': 'http://assets.maracoos.org'}
        ],
    },
    'MODELING_TESTBED': {
        'fullname': 'IOOS Coastal and Ocean Modeling Testbed',
        'provider_type': 'national',
        'banner': '/static/img/ioos.png',
        'description': 'IOOS Coastal and Ocean Modeling Testbed',
        'links': [
            {'title': 'U.S. IOOS Coastal and Ocean Modeling Testbed',
             'url': 'http://www.ioos.noaa.gov/modeling/testbed.html'}
        ]
    },
    'NANOOS': {
        'fullname': 'Northwest Association of Networked Ocean Observing Systems',
        'provider_type': 'regional',
        'banner': '/static/img/ra/nanoos.png',
        'description': 'The Northwest Association of Networked Ocean Observing Systems (NANOOS) is the Regional Association of the national Integrated Ocean Observing System (IOOS) in the Pacific Northwest, primarily Washington and Oregon. NANOOS has strong ties with the observing programs in Alaska and British Columbia through our common purpose and the occasional overlap of data and products.',
        'links': [
            {'title':'NANOOS Site', 'url': 'http://www.nanoos.org'},
            {'title':'NANOOS Visualization System (NVS)', 'url': 'http://nvs.nanoos.org'},
        ],
    },
    'NERACOOS': {
        'fullname':'Northeastern Regional Association of Coastal and Ocean Observing Systems',
        'provider_type': 'regional',
        'banner':'/static/img/ra/neracoos.png',
        'description':'NERACOOS, the Northeastern Regional Association of Coastal Ocean Observing Systems, is collecting and delivering quality and timely ocean and weather information to users throughout the Northeast United States and Canadian Maritimes. To achieve this, NERACOOS supports integrated coastal and ocean observing and modeling activities that feed user defined information products. NERACOOS works collaboratively with regional and local partners including the Northeast Regional Ocean Council (NROC), a state and federal partnership created by the six New England governors.',
        'links': [
            {'title':'NERACOOS Site', 'url': 'http://www.neracoos.org/'},
            {'title':'NERACOOS Real-Time Data Portal', 'url': 'http://www.neracoos.org/realtime_map'},
        ]
    },
    'PacIOOS': {
        'fullname':'Pacific Islands Ocean Observing System',
        'provider_type': 'regional',
        'banner':'/static/img/ra/pacioos.jpg',
        'description':'PacIOOS is one of eleven regional observing programs in the U.S. that are supporting the emergence of the U.S. Integrated Ocean Observing System (IOOS) under the National Oceanographic Partnership Program (NOPP).  The PacIOOS region includes the U.S. Pacific Region (Hawaii, Guam, American Samoa, Commonwealth of the Northern Mariana Islands), the Pacific nations in Free Association with the U.S. (Republic of the Marshall Islands, Federated States of Micronesia, Republic of Palau), and the U.S. Minor Outlying Islands (Howland, Baker, Johnston, Jarvis, Kingman, Palmyra, Midway, Wake).',
        'links': [
            {'title':'PacIOOS Site', 'url': 'http://www.pacioos.org'},
        ]
    },
    'SCCOOS': {
        'fullname':'Southern California Coastal Ocean Observing System',
        'provider_type': 'regional',
        'description':'SCCOOS brings together coastal observations in the Southern California Bight to provide information necessary to address issues in climate change, ecosystem preservation and management, coastal water quality, maritime operations, coastal hazards and national security.  As a science-based decision support system, SCCOOS works interactively with local, state and federal agencies, resource managers, industry, policy makers, educators, scientists and the general public to provide data, models and products that advance our understanding of the current and future state of our coastal and global environment.',
        'links': [
            {'title':'SCCOOS Site', 'url': 'http://www.sccoos.org'},
        ]
    },
    'SECOORA': {
        'fullname':'Southeast Coastal Ocean Observing Regional Association',
        'provider_type': 'regional',
        'banner':'/static/img/ra/secoora.png',
        'description':'SECOORA, the Southeast Coastal Ocean Observing Regional Association, is the regional solution to integrating coastal and ocean observing data and information in the Southeast United States.  SECOORA is a 501(c)(3) nonprofit incorporated in September 2007 that coordinates coastal and ocean observing activities, and facilitates continuous dialogue among stakeholders so that the benefits from the sustained operation of a coastal and ocean observing system can be realized.',
        'links': [
            {'title':'SECOORA Site', 'url': 'http://secoora.org/'},
            {'title':'SECOORA Data Portal', 'url': 'http://secoora.org/maps/'},
            {'title':'SECOORA Asset Inventory', 'url': 'http://inventory.secoora.org/'},
        ]
    },
    'NOAA-CO-OPS': {
        'fullname': 'NOAA Center for Operational Oceanographic Products and Services',
        'provider_type': 'national',
        'banner':'/static/img/np/NOAA-Transparent-Logo.png',
        'description': 'NOAA Center for Operational Oceanographic Products and Services',
        'links': [
            {'title': 'NOAA Tides and Currents', 'url': 'tidesandcurrents.noaa.gov'}
        ]
    },
    'USACE': {
        'fullname': 'US Army Corps of Engineers',
        'provider_type': 'national',
        #can only find an SVG logo presently
        'banner':'/static/img/np/United_States_Army_Corps_of_Engineers_logo.svg',
        'description':'US Army Corps of Engineers',
        'links': [
            {'title': 'US Army Corps of Engineers',
             'url': 'http://www.usace.army.mil'}
        ]

    },
    'NAVY': {
        'fullname':'United States Navy',
        'provider_type': 'national',
        'banner':'/static/img/np/logoNavy.jpg',
        'description':'United States Navy',
        'links': [
            {'title': 'US Navy Site', 'url': 'www.navy.mil'},
        ]
    },
    'NOAA-NDBC': {
        'fullname': 'NOAA National Data Buoy Center',
        'provider_type': 'national',
        'banner':'/static/img/np/NOAA-Transparent-Logo.png',
        'description': 'NOAA National Data Buoy Center',
        'links': [
            {'title': 'NDBC Site', 'url': 'http://www.ndbc.noaa.gov'}
        ]
    },
    'USGS-CMGP': {
        'fullname':'United States Geological Survey',
        'provider_type': 'national',
        'banner':'/static/img/np/usgs-logo-color.jpg',
        'description': 'USGS- Science for a Changing World',
        'links': [
            {'title': 'USGS Site', 'url': 'www.usgs.gov'}
        ]
    },
    'Other': {
        'provider_type': 'national',
    },
}

@app.route('/ras/')
def ras():
    return redirect('/')

@app.route('/providers/<path:provider>', methods=['GET'])
def show_ra(provider):
    if not provider in region_map:
        return redirect('/')

    # get numbers for the RA
    service_counts = db.Service.count_types_by_provider()
    dataset_counts = db.Dataset.count_types_by_provider()

    provider_service_count = service_counts.get(provider, {}).get('_all', 0)
    provider_dataset_count = dataset_counts.get(provider, {}).get('_all', 0)

    # get tls for this RA
    tlds = db.Service.find({'data_provider':provider, 'active':True}).distinct('tld')

    # get provider extra info from dictionary
    pi = provider_info.get(provider, {})

    return render_template("show_ra.html",
                           pi=pi,
                           provider=provider,
                           providers=region_map.keys(),
                           provider_service_count=provider_service_count,
                           tlds=tlds,
                           provider_dataset_count=provider_dataset_count)

