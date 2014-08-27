var SERVICE_MAPPINGS = {
    "NOS/CO-OPS" : "NOS-CO-OPS", // The slash disriupts proper routing
    "USGS/CMGP"  : "USGS-CMGP"
};

var URL_MAPPINGS = {
    "NOS-CO-OPS" : "NOS/CO-OPS", // The slash disriupts proper routing
    "USGS-CMGP"  : "USGS/CMGP"
}


/*
 * Takes an array of service names and returns an array of sanitized service
 * names.  There are some service names that invalidate the routing of Flask or
 * have illegal characters.
 */
function sanitizeServiceUrl(serviceNames) {
    console.log(serviceNames);
    if(!serviceNames || !serviceNames.length) {
        return "null";
    }
    var services = [];
    serviceNames.forEach(function(name) {
        console.log("Looking at " + name);
        if(name in SERVICE_MAPPINGS) {
            services.push(SERVICE_MAPPINGS[name]);
        } else {
            services.push(name);
        }
    });
    return services;
};


/*
 * Converts the comma separated string component of the URL route into an array
 * of proper service entries
 */
function urlToServiceArray(urlComponent) {
    var services = [];

    console.log(urlComponent);
    if(!urlComponent) {
        return "null";
    }
    urlComponent.split(',').forEach(function(name) {
        if(name in URL_MAPPINGS) {
            services.push(URL_MAPPINGS[name]);
        } else {
            services.push(name);
        }
    });
    return services;
}



