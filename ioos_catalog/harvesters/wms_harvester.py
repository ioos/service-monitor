#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
ioos_catalog/harvesters/wms_harvester.py

Harvester for WMS
'''
from ioos_catalog.harvesters.harvester import Harvester


class WmsHarvester(Harvester):

    def __init__(self, service):
        Harvester.__init__(self, service)

    def harvest(self):
        pass

