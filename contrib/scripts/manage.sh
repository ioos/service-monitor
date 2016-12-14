#!/bin/bash
export FLASK_ENV=PRODUCTION

cd /service-monitor

python manage.py $@
