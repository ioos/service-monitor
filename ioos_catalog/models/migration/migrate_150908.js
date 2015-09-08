/*
 * Adds indexes
 */

db.datasets.createIndex({"services.name":"text", "services.description":"text"});
db.datasets.createIndex({"services.data_provider":1});
