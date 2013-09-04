from fabric.api import *
from fabric.contrib.files import *
import os
from copy import copy
import time
import urlparse

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
    env.user = "kwilcox"
def monitoring():
    env.user = "monitoring"

def deploy():
    stop_supervisord()

    monitoring()
    with cd(code_dir):
        run("git pull origin master")
        update_supervisord()
        update_libs()
        create_index()
        start_supervisord()
        run("supervisorctl -c ~/supervisord.conf start all")

def update_supervisord():
    monitoring()
    run("pip install supervisor")
    upload_template('deploy/supervisord.conf', '/home/monitoring/supervisord.conf', context=copy(env), use_jinja=True, use_sudo=False, backup=False, mirror_local_mode=True)

def update_libs(paegan=None):
    monitoring()
    with cd(code_dir):
        with settings(warn_only=True):
            run("pip install -r requirements.txt")

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
            run("kill -QUIT $(ps aux | grep supervisord | grep -v grep | awk '{print $2}')")

    kill_pythons()

def kill_pythons():
    admin()
    with settings(warn_only=True):
        sudo("kill -QUIT $(ps aux | grep python | grep -v supervisord | awk '{print $2}')")

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

