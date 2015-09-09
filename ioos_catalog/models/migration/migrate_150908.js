/*
 * Adds indexes
 */

db.datasets.createIndex({"services.name":"text", "services.description":"text"});
db.datasets.createIndex({"services.data_provider":1});
db.services.createIndex({"name":"text"});
db.services.createIndex({"data_provider":1});
db.services.createIndex({"service_type":1});
