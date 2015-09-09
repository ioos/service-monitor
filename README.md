The IOOS Catalog
=======

A web based catalog of IOOS services and datasets, available at http://catalog.ioos.us

The Catalog obtains all service URLs from the metadata managed via [IOOS Service Registry](http://github.com/ioos/registry) and accessed through the [ESRI Geoportal Server hosted by NGDC](http://www.ngdc.noaa.gov/geoportal/).  See the [registry](http://github.com/ioos/registry) documentation for instructions for getting dataset metadata into the Service Registry.

Development
===

### Get a local copy

```
git clone https://github.com/ioos/catalog/
```

### Get MongoDB

#### Mac

```
brew install mongodb
```

It's highly encouraged to get [Robomongo](http://robomongo.org/download.html) as well.

### Setup a Virtualenv for the IOOS Catalog

Assuming you have `virtualenv_wrapper`

```
mkvirtualenv --no-site-packages catalog
cd catalog
pip install -r requirements.txt
```

### Setup the fab file and ENV

_Obtained from an administrator of the project to ensure you can't alter production_

#### Clone the production database

```
source env
fab -c .fab db_snapshot
```
### Get Redis

#### Mac

```
brew install redis
```

Run Redis

### Run the catalog

```
foreman start
```

# IOOS Website Mission Statement

IOOS.gov is where we tell the IOOS and OCGL story, through visually compelling
imagery and storytelling. We inspire visitors by providing easy access to
engaging, accessible, and dynamic OCGL data, news, and blue technology for
stakeholders in industry, education, government and for curious citizens.

