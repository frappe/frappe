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
form_dict = getattr(frappe.local, 'form_dict', None)


def get_logger(module, with_more_info=True):
	if module in frappe.loggers:
		return frappe.loggers[module]

	if not module:
		module = "frappe"

	logfile = module + '.log'
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
		record.msg = get_more_info_for_log() + text_type(record.msg)
		return True

def get_more_info_for_log():
	'''Adds Site, Form Dict into log entry'''
	more_info = []

	if site:
		more_info.append('Site: {0}'.format(site))

	form_dict = getattr(frappe.local, 'form_dict', None)
	if form_dict:
		more_info.append('Form Dict: {0}'.format(frappe.as_json(form_dict)))

	if more_info:
		# to append a \n
		more_info = more_info + ['']

	return '\n'.join(more_info)

def set_log_level(level):
	'''Use this method to set log level to something other than the default DEBUG'''
	frappe.log_level = getattr(logging, (level or '').upper(), None) or default_log_level
	frappe.loggers = {}
