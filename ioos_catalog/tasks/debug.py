#!/usr/bin/env python
from ioos_catalog import app

import functools

def debug_wrapper(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            app.logger.exception("Exception Caught")
            raise
    return wrapper

