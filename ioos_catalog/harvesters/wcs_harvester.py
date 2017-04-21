#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
ioos_catalog/harvesters/wcs_harvester.py

Harvester for WCS
'''
from ioos_catalog.harvesters.harvester import Harvester


class WcsHarvester(Harvester):

    def __init__(self, service):
        Harvester.__init__(self, service)

    def harvest(self):
        pass
