# imports - standard imports
import logging
import os
from copy import deepcopy
from logging.handlers import RotatingFileHandler
from typing import Literal

# imports - module imports
import frappe
from frappe.utils import get_sites

default_log_level = logging.WARNING if frappe._dev_server else logging.ERROR
stream_logging = os.environ.get("FRAPPE_STREAM_LOGGING")


def create_handler(
	module, site=None, max_size: int = 100_000, file_count: int = 20, stream_only: bool = False
):
	"""Create and return a Frappe-specific logging handler."""
	formatter = logging.Formatter(f"%(asctime)s %(levelname)s {module} %(message)s")

	if stream_only:
		handler = logging.StreamHandler()
	else:
		logfile = f"{module}.log"
		log_filename = os.path.join("..", "logs", logfile)
		handler = RotatingFileHandler(log_filename, maxBytes=max_size, backupCount=file_count)

	handler.setFormatter(formatter)

	if site and not stream_only:
		sitelog_filename = os.path.join(site, "logs", logfile)
		site_handler = RotatingFileHandler(sitelog_filename, maxBytes=max_size, backupCount=file_count)
		site_handler.setFormatter(formatter)
		return [handler, site_handler]

	return [handler]


def get_logger(
	module=None,
	with_more_info: bool = False,
	allow_site: bool = True,
	filter=None,
	max_size: int = 100_000,
	file_count: int = 20,
	stream_only=stream_logging,
) -> "logging.Logger":
	"""Return Application Logger for your given module.

	Args:
	        module (str, optional): Name of your logger and consequently your log file. Defaults to None.
	        with_more_info (bool, optional): Will log the form dict using the SiteContextFilter. Defaults to False.
	        allow_site ((str, bool), optional): Pass site name to explicitly log under it's logs. If True and unspecified, guesses which site the logs would be saved under. Defaults to True.
	        filter (function, optional): Add a filter function for your logger. Defaults to None.
	        max_size (int, optional): Max file size of each log file in bytes. Defaults to 100_000.
	        file_count (int, optional): Max count of log files to be retained via Log Rotation. Defaults to 20.
	        stream_only (bool, optional): Whether to stream logs only to stderr (True) or use log files (False). Defaults to False.

	Return a Python logger object with Site and Bench level logging capabilities.
	"""

	if allow_site is True:
		site = getattr(frappe.local, "site", None)
	elif allow_site in get_sites():
		site = allow_site
	else:
		site = False

	logger_name = "{}-{}".format(module, site or "all")

	try:
		return frappe.loggers[logger_name]
	except KeyError:
		pass

	if not module:
		module = "frappe"
		with_more_info = True

	logger = logging.getLogger(logger_name)
	logger.setLevel(frappe.log_level or default_log_level)
	logger.propagate = False

	handlers = create_handler(module, site, max_size, file_count, stream_only)
	for handler in handlers:
		logger.addHandler(handler)

	if with_more_info:
		handlers[0].addFilter(SiteContextFilter())

	if filter:
		logger.addFilter(filter)

	frappe.loggers[logger_name] = logger

	return logger


class SiteContextFilter(logging.Filter):
	"""This is a filter which injects request information (if available) into the log."""

	def filter(self, record) -> bool:
		if "Form Dict" not in str(record.msg):
			site = getattr(frappe.local, "site", None)
			form_dict = sanitized_dict(getattr(frappe.local, "form_dict", None))
			record.msg = str(record.msg) + f"\nSite: {site}\nForm Dict: {form_dict}"
			return True


def set_log_level(level: Literal["ERROR", "WARNING", "WARN", "INFO", "DEBUG"]) -> None:
	"""Use this method to set log level to something other than the default DEBUG"""
	frappe.log_level = getattr(logging, (level or "").upper(), None) or default_log_level
	frappe.loggers = {}


def sanitized_dict(form_dict):
	if not isinstance(form_dict, dict):
		return form_dict

	sanitized_dict = deepcopy(form_dict)

	blocklist = [
		"password",
		"passwd",
		"secret",
		"token",
		"key",
		"pwd",
	]

	for k in sanitized_dict:
		for secret_kw in blocklist:
			if secret_kw in k:
				sanitized_dict[k] = "********"
	return sanitized_dict
