#!/usr/bin/env python
'''
ioos_catalog/util.py
A python module containing useful methods
'''

from urllib import urlencode
from flask import request
from math import ceil
from numbers import Number
from collections import Set, Mapping, deque
import sys

def build_links(item_count, current_page, page_limit, query=None):
    '''
    Returns a list of RFC-5988 compliant links given the pagination information
    https://github.com/davidcelis/api-pagination
    http://tools.ietf.org/html/rfc5988

    :param int item_count: Total number of items or records
    :param int current_page: The current page number (starting with 0)
    :param int page_limit: Total number of pages
    :param dict query: The additional query parameters that should be used to construct the URL
    :return: list of RFC-5988 compliant links
    :rtype: list
    '''
    base_url = request.url.split('?')[0]
    query = query or {}
    links = []
    last_page_count = int(ceil(item_count * 1.0 / page_limit))
    if current_page < last_page_count:
        links.append(build_link(base_url, query, current_page+2, 'next'))
    links.append(build_link(base_url, query, 1, 'first'))
    if current_page > 0:
        links.append(build_link(base_url, query, current_page, 'prev'))
    links.append(build_link(base_url, query, last_page_count, 'last'))
    return links

def build_link(base_url, query, page, rel):
    '''
    Returns a RFC-5988 compliant link
    :param str base_url: Base URL
    :param dict query: The URL query parameters
    :param int page: The page number
    :param str rel: The rel text
    :return: RFC-5988 compliant link
    :rtype: str
    '''
    query['page'] = page
    return '<%s>; rel="%s"' % (build_url(base_url, query), rel)


def build_url(url, query):
    '''
    If a query exists it concatenates the query string to the URL
    :param str url: URL
    :param dict query: URL Query parameters
    '''
    if query:
        url += '?' + urlencode(query)
    return url


zero_depth_bases = (basestring, Number, xrange, bytearray)
iteritems = 'iteritems'


def getsize(obj_0):
    """
    Recursively iterate to sum size of object & members.

    From https://stackoverflow.com/questions/449560/how-do-i-determine-the-size-of-an-object-in-python
    """
    def inner(obj, _seen_ids=set()):
        obj_id = id(obj)
        if obj_id in _seen_ids:
            return 0
        _seen_ids.add(obj_id)
        size = sys.getsizeof(obj)
        if isinstance(obj, zero_depth_bases):
            pass  # bypass remaining control flow and return
        elif isinstance(obj, (tuple, list, Set, deque)):
            size += sum(inner(i) for i in obj)
        elif isinstance(obj, Mapping) or hasattr(obj, iteritems):
            size += sum(inner(k) + inner(v) for k, v in getattr(obj, iteritems)())
        # Check for custom object instances - may subclass above too
        if hasattr(obj, '__dict__'):
            size += inner(vars(obj))
        if hasattr(obj, '__slots__'):  # can have __slots__ with __dict__
            size += sum(inner(getattr(obj, s)) for s in obj.__slots__ if hasattr(obj, s))
        return size
    return inner(obj_0)
