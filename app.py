from ioos_catalog import app
import os
from werkzeug.contrib.profiler import ProfilerMiddleware

if os.environ.get('APPLICATION_SETTINGS') == 'development.py':
    #app.config['PROFILE']=True
    #app.wsgi_app = ProfilerMiddleware(app.wsgi_app, restrictions=[10])

    app.run(host="0.0.0.0", port=3000, debug=True)
