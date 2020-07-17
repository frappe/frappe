# imports - compatibility imports
from __future__ import unicode_literals

# imports - standard imports
import logging
import os
from logging.handlers import RotatingFileHandler

# imports - third party imports
from six import text_type

# imports - module imports
import frappe


default_log_level = logging.DEBUG
site = getattr(frappe.local, 'site', None)


def get_logger(module, with_more_info=False, _site=None):
	"""Application Logger for your given module

	Args:
		module (str): Name of your logger and consequently your log file.
		with_more_info (bool, optional): Will log the form dict using the SiteContextFilter. Defaults to False.
		_site (str, optional): If set, validates the current site context with the passed value. The `frappe.web` logger uses this to determine that the application is logging information related to the logger called. Defaults to None.

	Returns:
		<class 'logging.Logger'>: Returns a Python logger object with Site and Bench level logging capabilities.
	"""
	global site

	def allow_site():
		return (_site and _site == site) or bool(site)

	if module in frappe.loggers:
		return frappe.loggers[module]

	if not module:
		module = "frappe"
		with_more_info = True

	logfile = module + '.log'
	site = getattr(frappe.local, 'site', None)
	LOG_FILENAME = os.path.join('..', 'logs', logfile)

	logger = logging.getLogger(module)
	logger.setLevel(frappe.log_level or default_log_level)
	logger.propagate = False

	formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
	handler = RotatingFileHandler(LOG_FILENAME, maxBytes=100_000, backupCount=20)
	logger.addHandler(handler)

	if allow_site():
		SITELOG_FILENAME = os.path.join(site, 'logs', logfile)
		site_handler = RotatingFileHandler(SITELOG_FILENAME, maxBytes=100_000, backupCount=20)
		site_handler.setFormatter(formatter)
		logger.addHandler(site_handler)

	if with_more_info:
		handler.addFilter(SiteContextFilter())

	handler.setFormatter(formatter)

	frappe.loggers[module] = logger

	return logger

class SiteContextFilter(logging.Filter):
	"""This is a filter which injects request information (if available) into the log."""
	def filter(self, record):
		if "Form Dict" not in text_type(record.msg):
			record.msg = text_type(record.msg) + "\nSite: {0}\nForm Dict: {1}".format(site, getattr(frappe.local, 'form_dict', None))
			return True

def set_log_level(level):
	'''Use this method to set log level to something other than the default DEBUG'''
	frappe.log_level = getattr(logging, (level or '').upper(), None) or default_log_level
	frappe.loggers = {}
