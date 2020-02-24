# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

from datetime import datetime, timezone
import json
import time
import traceback
import frappe
import os


MONITOR_REDIS_KEY = "monitor-transactions"


def start(transaction_type="request", method=None, kwargs=None):
	if frappe.conf.monitor:
		frappe.local.monitor = Monitor(
			transaction_type=transaction_type, method=method, kwargs=kwargs
		)


def stop():
	if frappe.conf.monitor and hasattr(frappe.local, "monitor"):
		frappe.local.monitor.dump()


def log_file():
	return os.path.join(frappe.utils.get_bench_path(), "logs", "monitor.json.log")


class Monitor:
	def __init__(self, transaction_type=None, method=None, kwargs=None):
		try:
			self.site = frappe.local.site
			self.timestamp = datetime.now(timezone.utc)
			self.transaction_type = transaction_type

			if self.transaction_type == "request":
				self.data = frappe.form_dict
				self.headers = dict(frappe.request.headers)
				self.method = frappe.request.method
				self.path = frappe.request.path
			else:
				self.kwargs = kwargs
				self.method = method
		except Exception:
			traceback.print_exc()

	def dump(self):
		try:
			timediff = datetime.now(timezone.utc) - self.timestamp
			# Obtain duration in microseconds
			self.duration = int(timediff.total_seconds() * 1000000)
			data = {
				"duration": self.duration,
				"site": self.site,
				"timestamp": self.timestamp.isoformat(sep=" "),
				"transaction_type": self.transaction_type,
			}

			if self.transaction_type == "request":
				update = {
					"data": self.data,
					"headers": self.headers,
					"method": self.method,
					"path": self.path,
				}
			else:
				update = {
					"kwargs": self.kwargs,
					"method": self.method,
				}
			data.update(update)
			json_data = json.dumps(data, sort_keys=True, default=str)
			store(json_data)
		except Exception:
			traceback.print_exc()


def store(json_data):
	if frappe.cache().llen(MONITOR_REDIS_KEY) >= 1000000:
		frappe.cache().ltrim(MONITOR_REDIS_KEY, len(logs) - 1, -1)
		frappe.cache().rpush(MONITOR_REDIS_KEY, json_data)
	else:
		frappe.cache().rpush(MONITOR_REDIS_KEY, json_data)


def flush():
	try:
		# Fetch all the logs without removing from cache
		logs = frappe.cache().lrange(MONITOR_REDIS_KEY, 0, -1)
		logs = list(map(frappe.safe_decode, logs))
		with open(log_file(), "a", os.O_NONBLOCK) as f:
			f.write("\n".join(logs))

		# Remove fetched entries from cache
		frappe.cache().ltrim(MONITOR_REDIS_KEY, len(logs) - 1, -1)
	except Exception:
		traceback.print_exc()
