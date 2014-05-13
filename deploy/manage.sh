#!/bin/bash

INSTALL_DIR=$HOME/ioos-service-monitor

source $HOME/.bash_profile
export $(cat $HOME/.env | xargs)

pushd $INSTALL_DIR
python $INSTALL_DIR/manage.py $@
popd

