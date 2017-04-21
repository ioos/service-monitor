#!/usr/bin/env python
# -*- coding: utf-8 -*-
'''
ioos_catalog/harvesters/harvester.py
'''
from datetime import datetime
from ioos_catalog.harvesters import context_decorator
from ioos_catalog import db


class Harvester(object):

    def __init__(self, service):
        self.service = service

    @context_decorator
    def save_ccheck_and_metadata(self, service_id, checker_name, ref_id, ref_type, scores, metamap):
        """
        Saves the result of a compliance checker scores and metamap document.

        Will be called by service/station derived methods.
        """
        if not (scores or metamap):
            return

        def res2dict(r):
            cl = []
            if getattr(r, 'children', None):
                cl = map(res2dict, r.children)

            return {'name': unicode(r.name),
                    'score': float(r.value[0]),
                    'maxscore': float(r.value[1]),
                    'weight': int(r.weight),
                    'children': cl}

        metadata = db.Metadata.find_one({'ref_id': ref_id})
        if metadata is None:
            metadata = db.Metadata()
            metadata.ref_id = ref_id
            metadata.ref_type = unicode(ref_type)

        if isinstance(scores, tuple):  # New API of compliance-checker
            scores = scores[0]
        cc_results = map(res2dict, scores)

        # @TODO: srsly need to decouple from cchecker
        score = sum(((float(r.value[0]) / r.value[1]) * r.weight for r in scores))
        max_score = sum((r.weight for r in scores))

        score_doc = {'score': float(score),
                     'max_score': float(max_score),
                     'pct': float(score) / max_score}

        update_doc = {'cc_score': score_doc,
                      'cc_results': cc_results,
                      'metamap': metamap}

        for mr in metadata.metadata:
            if mr['service_id'] == service_id and mr['checker'] == checker_name:
                mr.update(update_doc)
                break
        else:
            metarecord = {'service_id': service_id,
                          'checker': unicode(checker_name)}
            metarecord.update(update_doc)
            metadata.metadata.append(metarecord)

        metadata.updated = datetime.utcnow()
        metadata.save()

        return metadata
