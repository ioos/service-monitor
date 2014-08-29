
/*
 * Takes an array of service names and returns an array of sanitized service
 * names.  There are some service names that invalidate the routing of Flask or
 * have illegal characters.
 */
function sanitizeServiceUrl(serviceNames) {
    if(!serviceNames || !serviceNames.length) {
        return "null";
    }
    return serviceNames;
};


/*
 * Converts the comma separated string component of the URL route into an array
 * of proper service entries
 */
function urlToServiceArray(urlComponent) {
    var services = [];

    if(!urlComponent) {
        return "null";
    }
    return urlComponent.split(',');
}



