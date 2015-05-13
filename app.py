from ioos_catalog import app
import os
from werkzeug.contrib.profiler import ProfilerMiddleware

if __name__ == '__main__':
    app.run(host=app.config['HOST'], port=app.config['PORT'], debug=app.config['DEBUG'])
