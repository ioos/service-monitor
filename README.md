The IOOS Catalog
=======

A web based catalog of IOOS services and datasets, available at http://catalog.ioos.us

The IOOS Catalog registration process is described here:
https://geo-ide.noaa.gov/wiki/index.php?title=IOOS_Catalog_Registration_Process

Here's the sequence of events to get data loaded in to the catalog:

* Register new data service URL at the NGDC Collection Source table  - Day 1, manual
* Test metadata harvest happens - by 7:15 am on Day 2, automatic
* Approval of  new data service - Day 2, manual
* WAF is populated with new ISO record - Day 3 by 7:15 am, automatic
* Geoportal harvests records from WAF - Day 3 by 9 am, automatic
* IOOS Catalog queries Geoportal for all IOOS service URLs -?
* IOOS Catalog harvests from individual services and generates dataset records. - ?

After a service URL is approved, steps 4 and 5 occur daily at the same time.
