from flask import render_template, make_response, redirect
from ioos_service_monitor import app
#from ioos_service_monitor.views.helpers import requires_auth

@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

#@requires_auth
@app.route('/jobs', methods=['GET'])
def jobs():
    return redirect('/rq')

@app.route('/crossdomain.xml', methods=['GET'])
def crossdomain():
    domain = """
    <cross-domain-policy>
        <allow-access-from domain="*"/>
        <site-control permitted-cross-domain-policies="all"/>
        <allow-http-request-headers-from domain="*" headers="*"/>
    </cross-domain-policy>
    """
    response = make_response(domain)
    response.headers["Content-type"] = "text/xml"
    return response

