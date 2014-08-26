from ioos_catalog import app
import os
from werkzeug.contrib.profiler import ProfilerMiddleware

if os.environ.get('APPLICATION_SETTINGS') == 'development.py':
    #app.config['PROFILE']=True
    #app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[10])
    host = os.environ.get('APPLICATION_HOST', '0.0.0.0')
    port = int(os.environ.get('APPLICATION_PORT', 3000))

    app.run(host=host, port=port, debug=True)
