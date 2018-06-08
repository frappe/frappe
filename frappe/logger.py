#!/bin/env python
# -*- coding: utf-8 -*-
"""Logger."""
import logging
from logging.handlers import RotatingFileHandler


TAGS = ["frappe"]
LOGGER_APP_NAME = "FRAPPE"
# add extra field to logstash message
FILE_PATH = '../logs/frappe.log'


def get_logger(context=None):
    """
    Return Logger.

    Setup  Logger.
    """
    formatter = logging.Formatter("%(levelname)s [%(asctime)s]: %(message)s")

    handler = RotatingFileHandler(
        FILE_PATH, maxBytes=1000000, backupCount=20)
    handler.setFormatter(formatter)

    logger = logging.getLogger(LOGGER_APP_NAME)

    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)

    # def extra_logger(level, message, **kwargs):
    #     getattr(logger, level)(message, extra=context)

    return logger

log = get_logger()