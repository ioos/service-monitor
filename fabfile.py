from fabric.api import *
from fabric.contrib.files import *
import os
from copy import copy
import time
import urlparse
import shutil
import yaml

"""
    Call this with fab -c .fab TASK to pick up deploy variables
    Required variables in .fab file:
        mail_server = x
        mail_port = x
        mail_username = x
        mail_password = x
        mail_default_sender = x
        mailer_debug = x
        mail_default_to = x
        mail_default_list = x
        webpass = x
        secret_key = x
        mongo_db = x
        redis_db = x
"""

env.user = "monitoring"
code_dir = "/home/monitoring/ioos-service-monitor"
env.hosts = ['198.199.75.160']

def admin():
    env.user = os.environ.get('ADMIN_USER')

def monitoring():
    env.user = os.environ.get('IOOS_USER', "monitoring")

def maintenance():
    run('cp ioos_catalog/static/nomaintenance.html ioos_catalog/static/maintenance.html')

def clear_maintenance():
    run('rm ioos_catalog/static/maintenance.html')

def deploy():
    with cd(code_dir):
        maintenance()
    stop_supervisord()

    monitoring()
    with cd(code_dir):
        run("git pull origin master")
        update_supervisord()
        update_libs()
        update_crontab()
        #create_index()
        start_supervisord()
        run("supervisorctl -c ~/supervisord.conf start all")
        clear_maintenance()

def update_supervisord():
    monitoring()
    run("pip install supervisor")
    upload_template('deploy/supervisord.conf', '/home/monitoring/supervisord.conf', context=copy(env), use_jinja=True, use_sudo=False, backup=False, mirror_local_mode=True)

def update_libs(paegan=None):
    monitoring()
    with cd(code_dir):
        with settings(warn_only=True):
            run("pip install -r requirements.txt")

def update_crontab():
    # .env
    upload_template('deploy/dotenv', '/home/monitoring/.env', context=copy(env), use_jinja=True, use_sudo=False, backup=False, mirror_local_mode=True)

    # manage.sh
    put('deploy/manage.sh', '/home/monitoring/manage.sh')

    # crontab
    put('deploy/catalog_crontab.txt', '/home/monitoring/crontab.txt')
    run("crontab %s" % "/home/monitoring/crontab.txt")

def restart_nginx():
    admin()
    sudo("/etc/init.d/nginx restart")

def supervisord_restart():
    stop_supervisord()
    start_supervisord()

def stop_supervisord():
    monitoring()
    with cd(code_dir):
        with settings(warn_only=True):
            run("supervisorctl -c ~/supervisord.conf stop all")
            run("kill -QUIT $(ps aux | grep supervisord | grep monitoring | grep -v grep | awk '{print $2}')")

    kill_pythons()

def kill_pythons():
    admin()
    with settings(warn_only=True):
        sudo("kill -QUIT $(ps aux | grep python | grep monitoring | grep -v supervisord | awk '{print $2}')")

def start_supervisord():
    monitoring()
    with cd(code_dir):
        with settings(warn_only=True):
            run("supervisord -c ~/supervisord.conf")

def create_index():
    MONGO_URI = env.get('mongo_db')
    url = urlparse.urlparse(MONGO_URI)
    MONGODB_DATABASE = url.path[1:]

    # @TODO: this will likely error on first run as the collection won't exist
    run('mongo "%s" --eval "db.getCollection(\'stats\').ensureIndex({\'created\':-1})"' % MONGODB_DATABASE)
    run('mongo "%s" --eval "db.getCollection(\'metadatas\').ensureIndex({\'ref_id\':1, \'ref_type\':1})"' % MONGODB_DATABASE)

def db_snapshot():
    admin()
    MONGODB_DATABASE = PRODUCTION['MONGODB_DATABASE']

    backup_name = time.strftime('%Y-%m-%d')

    tmp = run('mktemp -d').strip()

    with cd(tmp):
        run('mongodump -d %s -o %s' % (MONGODB_DATABASE, backup_name))
        run('tar cfvz %s.tar.gz %s' % (backup_name, backup_name))
        get(remote_path="%s.tar.gz" % backup_name, local_path='db/%(path)s')

    run('rm -r %s' % tmp)

    # local restore
    with lcd('db'): 
        local('tar xfvz %s.tar.gz' % backup_name)
        local('mongorestore -d catalog-%s %s' % (backup_name, os.path.join(backup_name, MONGODB_DATABASE)))

def reload():
    with open('config.yml') as f:
        __config_dict__ = yaml.load(f)
    if os.path.exists('config.local.yml'):
        with open('config.local.yml') as f:
            __config_dict__.update(yaml.load(f))
    globals().update(__config_dict__)

reload() # Initialize the globals on the first load of this module
