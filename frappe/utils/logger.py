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
from frappe.utils import get_sites

default_log_level = logging.DEBUG


def get_logger(
	module=None, with_more_info=False, allow_site=True, filter=None, max_size=100_000, file_count=20
):
	"""Application Logger for your given module

	Args:
	        module (str, optional): Name of your logger and consequently your log file. Defaults to None.
	        with_more_info (bool, optional): Will log the form dict using the SiteContextFilter. Defaults to False.
	        allow_site ((str, bool), optional): Pass site name to explicitly log under it's logs. If True and unspecified, guesses which site the logs would be saved under. Defaults to True.
	        filter (function, optional): Add a filter function for your logger. Defaults to None.
	        max_size (int, optional): Max file size of each log file in bytes. Defaults to 100_000.
	        file_count (int, optional): Max count of log files to be retained via Log Rotation. Defaults to 20.

	Returns:
	        <class 'logging.Logger'>: Returns a Python logger object with Site and Bench level logging capabilities.
	"""

	if allow_site is True:
		site = getattr(frappe.local, "site", None)
	elif allow_site in get_sites():
		site = allow_site
	else:
		site = False

	logger_name = "{0}-{1}".format(module, site or "all")

	try:
		return frappe.loggers[logger_name]
	except KeyError:
		pass

	if not module:
		module = "frappe"
		with_more_info = True

	logfile = module + ".log"
	log_filename = os.path.join("..", "logs", logfile)

	logger = logging.getLogger(logger_name)
	logger.setLevel(frappe.log_level or default_log_level)
	logger.propagate = False

	formatter = logging.Formatter("%(asctime)s %(levelname)s {0} %(message)s".format(module))
	handler = RotatingFileHandler(log_filename, maxBytes=max_size, backupCount=file_count)
	handler.setFormatter(formatter)
	logger.addHandler(handler)

	if site:
		sitelog_filename = os.path.join(site, "logs", logfile)
		site_handler = RotatingFileHandler(sitelog_filename, maxBytes=max_size, backupCount=file_count)
		site_handler.setFormatter(formatter)
		logger.addHandler(site_handler)

	if with_more_info:
		handler.addFilter(SiteContextFilter())

	if filter:
		logger.addFilter(filter)

	frappe.loggers[logger_name] = logger

	return logger


class SiteContextFilter(logging.Filter):
	"""This is a filter which injects request information (if available) into the log."""

	def filter(self, record):
		if "Form Dict" not in text_type(record.msg):
			site = getattr(frappe.local, "site", None)
			form_dict = getattr(frappe.local, "form_dict", None)
			record.msg = text_type(record.msg) + "\nSite: {0}\nForm Dict: {1}".format(site, form_dict)
			return True


def set_log_level(level):
	"""Use this method to set log level to something other than the default DEBUG"""
	frappe.log_level = getattr(logging, (level or "").upper(), None) or default_log_level
	frappe.loggers = {}
