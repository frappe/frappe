from __future__ import unicode_literals
import frappe
import logging
import logging.config
import os
import json
from pprint import pformat

class ContextFilter(logging.Filter):
	"""
	This is a filter which injects request information (if available) into the log.
	"""

	def filter(self, record):
		record.form_dict = pformat(getattr(frappe.local, 'form_dict', None))
		record.site = getattr(frappe.local, 'site', None)
		record.tb = frappe.utils.get_traceback()
		return True

def setup_logging():
	conf = frappe.get_site_config(sites_path=os.environ.get('SITES_PATH', '.'))
	if conf.logging_conf:
		logging_conf = conf.logging_conf
	else:
		logging_conf = {
			"version": 1,
			"disable_existing_loggers": True,
			"filters": {
				"context_filter": {
					"()": "frappe.setup_logging.ContextFilter"
				}
			},
			"formatters": {
				"site_wise": {
					"format": "\n%(asctime)s %(message)s \n site: %(site)s\n form: %(form_dict)s\n\n%(tb)s\n--------------"
				}
			},
			"loggers": {
				"frappe": {
					"level": "INFO",
					"propagate": False,
					"filters": ["context_filter"],
					"handlers": ["request_exception"]
				}
			},
			"handlers": {
				"request_exception": {
					"level": "ERROR",
					"formatter": "site_wise",
					"class": "logging.StreamHandler",
				}
			}
		}
		if conf.request_exception_log_file:
			logging_conf.update({
				"handlers": {
					"request_exception": {
						"level": "ERROR",
						"formatter": "site_wise",
						"class": "logging.handlers.WatchedFileHandler",
						"filename": conf.request_exception_log_file
					}
				}
			})
	logging.config.dictConfig(logging_conf)
