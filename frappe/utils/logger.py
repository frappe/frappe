from __future__ import unicode_literals
import frappe
import logging
from logging.handlers import RotatingFileHandler
from six import text_type

default_log_level = logging.DEBUG
LOG_FILENAME = '../logs/frappe.log'

def get_logger(module, with_more_info=True):
	if module in frappe.loggers:
		return frappe.loggers[module]

	formatter = logging.Formatter('[%(levelname)s] %(asctime)s | %(pathname)s:\n%(message)s')
	# handler = logging.StreamHandler()

	handler = RotatingFileHandler(
		LOG_FILENAME, maxBytes=100000, backupCount=20)
	handler.setFormatter(formatter)

	if with_more_info:
		handler.addFilter(SiteContextFilter())

	logger = logging.getLogger(module)
	logger.setLevel(frappe.log_level or default_log_level)
	logger.addHandler(handler)
	logger.propagate = False

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
	site = getattr(frappe.local, 'site', None)
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

