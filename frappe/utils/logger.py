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


def get_logger(module, with_more_info=False):
	global site
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
#
	if site:
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
