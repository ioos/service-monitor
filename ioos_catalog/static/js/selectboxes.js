/*
 * selectboxes.js
 *
 * Shared code between the services and datasets endpoints that manage the
 * dynamic behavior of the multi-select boxes
 *
 * requires servicemappings.js for the constant(s)
 */



/*
* Returns the valid providers and filters
*/
function getValids() {
    var valid = {};
    valid.providers = [];
    valid.filters = [];

    $('#region-select option').each(function() {
      valid.providers.push($(this).val());
    });

    $('#filter-select option').each(function() {
      valid.filters.push($(this).val());
    });

    return valid;
}

function getSelected() {
    var selected = {};
    /* Split the URL up to parse out the provider and filter components */
    var currentURL = document.URL;
    var filters = currentURL.split("/filter/")[1]; /* Split on the /filter/ */
    if(typeof filters == 'undefined') { // no need to go any further
        return selected;
    }
    var filterSplit = filters.split("/");
    selected.providers = urlToServiceArray(filterSplit[0]); /* Some services have illegal characters in their names */
    if(filterSplit.length > 1) {
        selected.filters = filterSplit[1].split(",");
    }



    return selected;
}




function updateSelectBoxes() {
    var valid = getValids();
    var selected = getSelected();
    var validProviders = [];
    /* Now go through each of the options and make sure the providers are in the options */
    for(var i in selected.providers) {
        if(valid.providers.indexOf(selected.providers[i]) >= 0) {
          validProviders.push(selected.providers[i]);
        }
    }
    /* Update them appropriately */
    $('#region-select').val(validProviders);
    $('#region-select').trigger("chosen:updated");

    /* Do the same for the filters */
    var validFilters = [];
    for(var i in selected.filters) {
        if(valid.filters.indexOf(selected.filters[i]) >= 0) {
            validFilters.push(selected.filters[i]);
        }
    }
    $('#filter-select').val(validFilters);
    $('#filter-select').trigger("chosen:updated");
}

function applyFilter(urlBase) {
    var regionSelect = $('#region-select').val();
    var regionString = sanitizeServiceUrl(regionSelect);
    var filterType = $('#filter-select').val();
    var filterString = null;


    if(typeof filterType != 'undefined' && filterType !== null) {
        filterString = filterType.join(",");
    }

    var url = urlBase + regionString;
    if(filterType != "null") {
        url += "/" + filterType;
    }
    window.location = url;
}

function resetFilter(urlBase) {
    var url = urlBase;
    window.location = url;
}
