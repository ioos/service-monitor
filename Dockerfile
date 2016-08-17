FROM phusion/baseimage:0.9.18

MAINTAINER "Benjamin Adams <ben.adams@rpsgroup.com>"

RUN DEBIAN_FRONTEND=noninteractive apt-get update -y && \
    apt-get install -q -y git \
    libgeos-dev \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    libhdf5-dev \
    libcurl4-openssl-dev \
    autoconf \
    python-dev \
    python-pip \
    libgdal-dev \
    libudunits2-dev \
    libyaml-dev \
    redis-tools \
    libfreetype6-dev

RUN curl 'ftp://ftp.unidata.ucar.edu/pub/netcdf/netcdf-4.4.1.tar.gz' -o netcdf-4.4.1.tar.gz \
    && tar -zxvf netcdf-4.4.1.tar.gz \
    && cd netcdf-4.4.1 \
    && ./configure --prefix=/usr \
    && make \
    && make install \
    && cd .. \
    && rm -rf netcdf-4*

RUN mkdir /service-monitor
COPY ioos_catalog /service-monitor/ioos_catalog
RUN mkdir /service-monitor/logs
COPY app.py config.yml console manage.py requirements.txt web worker /service-monitor/
RUN rm -rf /var/lib/apt/lists/*
RUN pip install -U pip
RUN pip install numpy && \
    pip install gunicorn
RUN pip install -r /service-monitor/requirements.txt
WORKDIR /service-monitor
COPY ./contrib/docker/my_init.d /etc/my_init.d
CMD /sbin/my_init -- gunicorn -w 2 -b 0.0.0.0:3000 app:app
