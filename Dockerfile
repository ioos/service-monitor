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
    liblapack3 \
    libfreetype6-dev

RUN curl 'ftp://ftp.unidata.ucar.edu/pub/netcdf/netcdf-4.4.1.tar.gz' -o netcdf-4.4.1.tar.gz \
    && tar -zxvf netcdf-4.4.1.tar.gz \
    && cd netcdf-4.4.1 \
    && ./configure --prefix=/usr \
    && make \
    && make install \
    && cd .. \
    && rm -rf netcdf-4*

RUN mkdir /service-monitor && \
    mkdir /service-monitor/logs && \
    mkdir /service-monitor/db

COPY app.py config.yml console manage.py requirements.txt web worker /service-monitor/
COPY ./contrib/scripts/install_python.sh ./contrib/scripts/install_captcha.sh /
RUN /install_python.sh && \
    /install_captcha.sh && \
    rm -rf /install_captcha.sh && \
    rm -rf /install_python.sh
RUN pip install numpy && \
    pip install scipy && \
    pip install gunicorn
RUN pip install -r /service-monitor/requirements.txt
COPY ioos_catalog /service-monitor/ioos_catalog
WORKDIR /service-monitor
COPY ./contrib/docker/my_init.d /etc/my_init.d
RUN rm -rf /var/lib/apt/lists/*
CMD /sbin/my_init -- gunicorn -w 2 -b 0.0.0.0:3000 app:app
