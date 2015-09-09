FORMAT: 1A
HOST: http://catalog.ioos.us/

# IOOS Catalog

The IOOS Catalog provides a simple public facing API that allows consumers to search for datasets and services within the IOOS Catalog data.

## API Notes

Each API endpoint that supports pagination (i.e. the collection endpoints) supports [RFC-5988 - Web Linking](https://tools.ietf.org/html/rfc5988) for pagination purposes.

# Group Datasets

Datasets represents a harvestable object either from SOS or from OPeNDAP. The
dataset object contains a list of services that point to it, which is often the
case for SOS services as they are federated and can share references to
stations.

## Datasets Collection [/api/dataset{?page,search,data_provider,active}]

A collection of dataset objects.

+ Parameters
  
    + page: 1 (number, optional) - The current page number

        + Default: `1`

    + search: swan (string, optional) - The search term
    + data_provider: NERACOOS (string, optional) - Filter by data provider
        + Members
            + `AOOS` - Alaska Ocean Observing System
            + `CARICOOS` - Caribbean Coastal Ocean Observing System
            + `CDIP` - Coastal Data Information Program
            + `CeNCOOS` - The Central and Northern California Ocean Observing System
            + `GCOOS` - Gulf of Mexico Ocean Observing System
            + `GLOS` - Great Lakes Observing System
            + `Glider_DAC` - IOOS Glider DAC
            + `HFradar_DAC` - IOOS High Frequency Radar DAC
            + `MARACOOS` - Mid-Atlantic Regional Association Coastal Ocean Observing System
            + `MODELING_TESTBED` - IOOS Coastal and Ocean Modeling Testbed
            + `NANOOS` - Northwest Association of Networked Ocean Observing Systems
            + `NAVY` - United States Navy
            + `NERACOOS` - Northeastern Regional Association of Coastal and Ocean Observing Systems
            + `NOAA-CO-OPS` - NOAA Center for Operational Oceanographic Products and Services
            + `NOAA-NDBC` - NOAA National Data Buoy Center
            + `Other` - Non-Federal or Regional providers
            + `PacIOOS` - Pacific Islands Ocean Observing System
            + `SCCOOS` - Southern California Coastal Ocean Observing System
            + `SECOORA` - Southeast Coastal Ocean Observing Regional Association
            + `USGS-CMGP` - United States Geological Survey
    + active: true (boolean, optional) - Only return active datasets
        + Default: true


### Find Datasets [GET]

Returns a JSON list of datasets for the query specified.

+ Response 200 (application/json)

    + Headers
        
            Link: <http://catalog.ioos.us/api/dataset?page=2>; rel="next", <http://catalog.ioos.us/api/dataset?page=1>; rel="first", <http://catalog.ioos.us/api/dataset?page=605>; rel="last"

    + Body

            [
              {
                "updated": {
                  "$date": 1441783929793
                },
                "uid": "http://www.neracoos.org/thredds/dodsC/WW3/NorthAtlantic.nc",
                "created": {
                  "$date": 1392071774215
                },
                "services": [
                  {
                    "updated": {
                      "$date": 1441783929793
                    },
                    "time_max": {
                      "$date": 1441886400000
                    },
                    "description": null,
                    "variables": [
                      "swp",
                      "dir",
                      "http://mmisw.org/ont/cf/parameter/sea_surface_wave_significant_height"
                    ],
                    "messages": [
                      "Could not get dataset name.  No global attribute named 'title'.",
                      "Could not get dataset description.  No global attribute named 'summary'.",
                      "Could not get dataset keywords.  No global attribute named 'keywords' or was not comma seperated list.",
                      "Variable hs was used to calculate geometry."
                    ],
                    "service_id": {
                      "$oid": "52f953b18c0db332e29277fb"
                    },
                    "service_type": "DAP",
                    "metadata_type": "ncml",
                    "keywords": [],
                    "data_provider": "NERACOOS",
                    "time_min": {
                      "$date": 1441713600000
                    },
                    "asset_type": "Regular Grid",
                    "name": null
                  }
                ],
                "active": true,
                "_id": {
                  "$oid": "52f9545e8c0db32a4ef41da7"
                }
              }
            ]

## Dataset [/api/dataset/{dataset_id}]

A single record for a dataset.

+ Parameters

    + dataset_id: 52f9545e8c0db32a4ef41da7 (string) - The ObjectId for the dataset

+ Attributes

    + active: true (boolean) - If this dataset is active and being actively harvested
    + services.name: ... (string)
    + services.description: ... (string) - Description of the dataset as registered through the service. 
    + services.data_provider: NERACOOS (string) - Data Provider of the service for which this dataset is available through.
    + services.variables: ... (array) - List of variables as available from the service endpoint

### Retrieve a Dataset [GET]

Returns a single JSON object for the dataset on record.

+ Response 200 (application/json)

        {
          "updated": {
            "$date": 1441783929793
          },
          "uid": "http://www.neracoos.org/thredds/dodsC/WW3/NorthAtlantic.nc",
          "created": {
            "$date": 1392071774215
          },
          "services": [
            {
              "updated": {
                "$date": 1441783929793
              },
              "time_max": {
                "$date": 1441886400000
              },
              "description": null,
              "variables": [
                "swp",
                "dir",
                "http://mmisw.org/ont/cf/parameter/sea_surface_wave_significant_height"
              ],
              "messages": [
                "Could not get dataset name.  No global attribute named 'title'.",
                "Could not get dataset description.  No global attribute named 'summary'.",
                "Could not get dataset keywords.  No global attribute named 'keywords' or was not comma seperated list.",
                "Variable hs was used to calculate geometry."
              ],
              "service_id": {
                "$oid": "52f953b18c0db332e29277fb"
              },
              "service_type": "DAP",
              "metadata_type": "ncml",
              "keywords": [],
              "data_provider": "NERACOOS",
              "time_min": {
                "$date": 1441713600000
              },
              "asset_type": "Regular Grid",
              "name": null
            }
          ],
          "active": true,
          "_id": {
            "$oid": "52f9545e8c0db32a4ef41da7"
          }
        }

# Group Services

A service record represents a single service endpoint from one of the IOOS
Catalog supported service types. Each service generally contains information
about "where can data be found". The individual services may also contain
metadata about the data available from that service endpoint. For example most
THREDDS endpoints (DAP) have a name and description that come from the original
netCDF files.

## Services Collection [/api/service{?page,search,data_provider,service_type,active}]

Returns a JSON list of services for the query specified.

+ Parameters
  
    + page: 1 (number, optional) - The current page number

        + Default: `1`

    + search: Erie (string, optional) - The search term
    + data_provider: GLOS (string, optional) - Filter by data provider
        + Members
            + `AOOS` - Alaska Ocean Observing System
            + `CARICOOS` - Caribbean Coastal Ocean Observing System
            + `CDIP` - Coastal Data Information Program
            + `CeNCOOS` - The Central and Northern California Ocean Observing System
            + `GCOOS` - Gulf of Mexico Ocean Observing System
            + `GLOS` - Great Lakes Observing System
            + `Glider_DAC` - IOOS Glider DAC
            + `HFradar_DAC` - IOOS High Frequency Radar DAC
            + `MARACOOS` - Mid-Atlantic Regional Association Coastal Ocean Observing System
            + `MODELING_TESTBED` - IOOS Coastal and Ocean Modeling Testbed
            + `NANOOS` - Northwest Association of Networked Ocean Observing Systems
            + `NAVY` - United States Navy
            + `NERACOOS` - Northeastern Regional Association of Coastal and Ocean Observing Systems
            + `NOAA-CO-OPS` - NOAA Center for Operational Oceanographic Products and Services
            + `NOAA-NDBC` - NOAA National Data Buoy Center
            + `Other` - Non-Federal or Regional providers
            + `PacIOOS` - Pacific Islands Ocean Observing System
            + `SCCOOS` - Southern California Coastal Ocean Observing System
            + `SECOORA` - Southeast Coastal Ocean Observing Regional Association
            + `USGS-CMGP` - United States Geological Survey
    + active: true (boolean, optional) - Only return active datasets
        + Default: true

    + service_type: DAP (string, optional) - Type of service
        
        + Members
            + `DAP` - OPeNDAP
            + `SOS` - OGC Sensor Observation Service
            + `WCS` - OGC Web Coverage Service
            + `WMS` - OGC Web Map Service


### Find Services [GET]

+ Response 200 (application/json)

    + Headers

            Link: <http://catalog.ioos.us/api/service?page=2>; rel="next", <http://catalog.ioos.us/api/service?page=1>; rel="first", <http://catalog.ioos.us/api/service?page=605>; rel="last"

    + Body

            [
                {
                    "_id": {
                        "$oid": "531b35978c0db36ff417affd"
                    },
                    "active": true,
                    "contact": "",
                    "created": {
                        "$date": 1394292119896
                    },
                    "data_provider": "NOAA-CO-OPS",
                    "extra_url": "http://opendap.co-ops.nos.noaa.gov/thredds/dodsC/LEOFS/fmrc/Aggregated_7_day_LEOFS_Fields_Forecast_best.ncd.html",
                    "interval": 3600,
                    "manual": false,
                    "metadata_url": null,
                    "name": "LEOFS -  Lake Erie Operational Forecast System - NOAA CO-OPS - POM",
                    "service_id": "gov.noaa.nos.co-ops:LEOFS/fmrc/Aggregated_7_day_LEOFS_Fields_Forecast_best.ncd",
                    "service_type": "DAP",
                    "tld": "opendap.co-ops.nos.noaa.gov",
                    "updated": {
                        "$date": 1441780435064
                    },
                    "url": "http://opendap.co-ops.nos.noaa.gov/thredds/dodsC/LEOFS/fmrc/Aggregated_7_day_LEOFS_Fields_Forecast_best.ncd"
                }
            ]

## Service [/api/service/{service_id}]

Returns a JSON object of a service record.

+ Parameters

    + service_id: 52f953e48c0db332e2927802 (string) - Service ObjectId

+ Attributes
    + active: true (boolean) - Whether this service is active and actively being harvested.
    + name: ... (string) - Name of the service endpoint
    + description: ... (string) - Description of the service endpoint
    + service_id: ... (string) - Identifier of the service endpoint
    + tld: ... (string) - Domain of the server where this service is hosted
    + service_type: DAP (string) - Type of service
    + url: ... (string) - URL of the service endpoint
    + extra_url: ... (string, optional) - Human digestible service endpoint

### Retrieve a Service [GET]

+ Response 200 (application/json)

        {
            "_id": {
                "$oid": "531b35978c0db36ff417affd"
            },
            "active": true,
            "contact": "",
            "created": {
                "$date": 1394292119896
            },
            "data_provider": "NOAA-CO-OPS",
            "extra_url": "http://opendap.co-ops.nos.noaa.gov/thredds/dodsC/LEOFS/fmrc/Aggregated_7_day_LEOFS_Fields_Forecast_best.ncd.html",
            "interval": 3600,
            "manual": false,
            "metadata_url": null,
            "name": "LEOFS -  Lake Erie Operational Forecast System - NOAA CO-OPS - POM",
            "service_id": "gov.noaa.nos.co-ops:LEOFS/fmrc/Aggregated_7_day_LEOFS_Fields_Forecast_best.ncd",
            "service_type": "DAP",
            "tld": "opendap.co-ops.nos.noaa.gov",
            "updated": {
                "$date": 1441780435064
            },
            "url": "http://opendap.co-ops.nos.noaa.gov/thredds/dodsC/LEOFS/fmrc/Aggregated_7_day_LEOFS_Fields_Forecast_best.ncd"
        }
