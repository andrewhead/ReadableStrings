#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import logging
import requests
import time


logging.basicConfig(level=logging.INFO, format="%(message)s")


default_requests_session = requests.Session()
default_requests_session.headers['User-Agent'] =\
    "Andrew Head (for academic research) <andrewhead@eecs.berekeley.edu>"


def make_request(method, *args, **kwargs):

    MAX_ATTEMPTS = 5
    RETRY_DELAY = 30
    try_again = True
    attempts = 0
    res = None

    def log_error(err_msg):
        logging.warn(
            "Error (%s) For API call %s, Args: %s, Kwargs: %s",
            str(err_msg), str(method), str(args), str(kwargs)
        )

    while try_again and attempts < MAX_ATTEMPTS:

        try:
            res = method(*args, **kwargs)
            if hasattr(res, 'status_code') and res.status_code not in [200]:
                log_error(str(res.status_code))
                res = None
            try_again = False
        except requests.exceptions.ConnectionError:
            log_error("ConnectionError")
        except requests.exceptions.ReadTimeout:
            log_error("ReadTimeout")

        if try_again:
            logging.warn("Waiting %d seconds for before retrying.", int(RETRY_DELAY))
            time.sleep(RETRY_DELAY)
            attempts += 1

    return res
