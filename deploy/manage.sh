#!/bin/bash

INSTALL_DIR=$HOME/ioos-service-monitor

source $HOME/.bash_profile
source $HOME/.env

python $INSTALL_DIR/manage.py $@

