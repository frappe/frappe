# -*- coding: utf-8 -*-
<<<<<<< HEAD
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
=======
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
>>>>>>> af3c4feb64 (feat: Monitor)
# MIT License. See license.txt

from __future__ import unicode_literals

<<<<<<< HEAD
from datetime import datetime
import json
import traceback
import frappe
import os
import uuid
import rq


MONITOR_REDIS_KEY = "monitor-transactions"
MONITOR_MAX_ENTRIES = 1000000
=======
from datetime import datetime, timezone
import json
import traceback
import frappe
import os
import uuid


MONITOR_REDIS_KEY = "monitor-transactions"
>>>>>>> af3c4feb64 (feat: Monitor)


def start(transaction_type="request", method=None, kwargs=None):
	if frappe.conf.monitor:
<<<<<<< HEAD
		frappe.local.monitor = Monitor(transaction_type, method, kwargs)


def stop(response=None):
	if hasattr(frappe.local, "monitor"):
		frappe.local.monitor.dump(response)
=======
		frappe.local.monitor = Monitor(
			transaction_type=transaction_type, method=method, kwargs=kwargs
		)


def stop():
	if frappe.conf.monitor and hasattr(frappe.local, "monitor"):
		frappe.local.monitor.dump()
>>>>>>> af3c4feb64 (feat: Monitor)


def log_file():
	return os.path.join(frappe.utils.get_bench_path(), "logs", "monitor.json.log")


class Monitor:
<<<<<<< HEAD
	def __init__(self, transaction_type, method, kwargs):
		try:
			self.data = frappe._dict(
				{
					"site": frappe.local.site,
					"timestamp": datetime.utcnow(),
					"transaction_type": transaction_type,
					"uuid": str(uuid.uuid4()),
				}
			)

			if transaction_type == "request":
				self.collect_request_meta()
			else:
				self.collect_job_meta(method, kwargs)
		except Exception:
			traceback.print_exc()

	def collect_request_meta(self):
		self.data.request = frappe._dict(
			{
				"ip": frappe.local.request_ip,
				"method": frappe.request.method,
				"path": frappe.request.path,
			}
		)

	def collect_job_meta(self, method, kwargs):
		self.data.job = frappe._dict({"method": method, "scheduled": False, "wait": 0})
		if "run_scheduled_job" in method:
			self.data.job.method = kwargs["job_type"]
			self.data.job.scheduled = True

		job = rq.get_current_job()
		if job:
			self.data.uuid = job.id
			waitdiff = self.data.timestamp - job.enqueued_at
			self.data.job.wait = int(waitdiff.total_seconds() * 1000000)

	def dump(self, response=None):
		try:
			timediff = datetime.utcnow() - self.data.timestamp
			# Obtain duration in microseconds
			self.data.duration = int(timediff.total_seconds() * 1000000)

			if self.data.transaction_type == "request":
				self.data.request.status_code = response.status_code
				self.data.request.response_length = int(response.headers.get("Content-Length", 0))

				if hasattr(frappe.local, "rate_limiter"):
					limiter = frappe.local.rate_limiter
					self.data.request.counter = limiter.counter
					if limiter.rejected:
						self.data.request.reset = limiter.reset

			self.store()
		except Exception:
			traceback.print_exc()

	def store(self):
		if frappe.cache().llen(MONITOR_REDIS_KEY) > MONITOR_MAX_ENTRIES:
			frappe.cache().ltrim(MONITOR_REDIS_KEY, 1, -1)
		serialized = json.dumps(self.data, sort_keys=True, default=str)
		frappe.cache().rpush(MONITOR_REDIS_KEY, serialized)
=======
	def __init__(self, transaction_type=None, method=None, kwargs=None):
		try:
			self.site = frappe.local.site
			self.timestamp = datetime.now(timezone.utc)
			self.transaction_type = transaction_type
			self.uuid = uuid.uuid4()

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
				"uuid": self.uuid,
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
<<<<<<< HEAD
	if frappe.cache().llen(MONITOR_REDIS_KEY) >= 1000000:
		frappe.cache().ltrim(MONITOR_REDIS_KEY, len(logs) - 1, -1)
		frappe.cache().rpush(MONITOR_REDIS_KEY, json_data)
	else:
		frappe.cache().rpush(MONITOR_REDIS_KEY, json_data)
>>>>>>> af3c4feb64 (feat: Monitor)
=======
	MAX_LOGS = 1000000
	if frappe.cache().llen(MONITOR_REDIS_KEY) > MAX_LOGS:
		frappe.cache().ltrim(MONITOR_REDIS_KEY, 1, -1)
	frappe.cache().rpush(MONITOR_REDIS_KEY, json_data)
>>>>>>> 96d9f2624b (fix(monitor): Maintain MAX_LOG entries in cache)


def flush():
	try:
		# Fetch all the logs without removing from cache
		logs = frappe.cache().lrange(MONITOR_REDIS_KEY, 0, -1)
<<<<<<< HEAD
		if logs:
			logs = list(map(frappe.safe_decode, logs))
			with open(log_file(), "a", os.O_NONBLOCK) as f:
				f.write("\n".join(logs))
				f.write("\n")
			# Remove fetched entries from cache
			frappe.cache().ltrim(MONITOR_REDIS_KEY, len(logs) - 1, -1)
=======
		logs = list(map(frappe.safe_decode, logs))
		with open(log_file(), "a", os.O_NONBLOCK) as f:
			f.write("\n".join(logs))

		# Remove fetched entries from cache
		frappe.cache().ltrim(MONITOR_REDIS_KEY, len(logs) - 1, -1)
>>>>>>> af3c4feb64 (feat: Monitor)
	except Exception:
		traceback.print_exc()
