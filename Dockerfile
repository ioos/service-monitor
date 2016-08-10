FROM phusion/baseimage:0.9.18

MAINTAINER "Benjamin Adams <ben.adams@rpsgroup.com>"

RUN DEBIAN_FRONTEND=noninteractive apt-get update -y && \
    apt-get install -q -y git libgeos-dev libxml2-dev libxslt1-dev \
                          libhdf5-dev libnetcdf-dev python-dev python-pip \
                          libgdal-dev libudunits2-dev libyaml-dev
RUN mkdir /service-monitor
COPY . /service-monitor
COPY requirements.txt service_monitor/
RUN DEBIAN_FRONTEND=noninteractive apt-get install -q -y gfortran liblapack-dev

RUN pip install setuptools
#RUN pip install -U pip && 
RUN pip install numpy gunicorn && \
    pip install -r service_monitor/requirements.txt
RUN cp /service-monitor/docker_config.yml /service-monitor/config.local.yml
WORKDIR /service-monitor
#CMD python app.py run
CMD gunicorn -w 2 -b 0.0.0.0:3000 app:app
