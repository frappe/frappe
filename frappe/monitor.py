# Copyright (c) 2020, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import datetime
import json
import os
import traceback
import uuid

import pytz
import rq

import nts
from nts.utils.data import cint
from nts.utils.synchronization import filelock

MONITOR_REDIS_KEY = "monitor-transactions"
MONITOR_MAX_ENTRIES = 1000000


def start(transaction_type="request", method=None, kwargs=None):
	if nts.conf.monitor:
		nts.local.monitor = Monitor(transaction_type, method, kwargs)


def stop(response=None):
	if hasattr(nts.local, "monitor"):
		nts.local.monitor.dump(response)


def add_data_to_monitor(**kwargs) -> None:
	"""Add additional custom key-value pairs along with monitor log.
	Note: Key-value pairs should be simple JSON exportable types."""
	if hasattr(nts.local, "monitor"):
		nts.local.monitor.add_custom_data(**kwargs)


def get_trace_id() -> str | None:
	"""Get unique ID for current transaction."""
	if monitor := getattr(nts.local, "monitor", None):
		return monitor.data.uuid


def log_file():
	return os.path.join(nts.utils.get_bench_path(), "logs", "monitor.json.log")


class Monitor:
	__slots__ = ("data",)

	def __init__(self, transaction_type, method, kwargs):
		try:
			self.data = nts._dict(
				{
					"site": nts.local.site,
					"timestamp": datetime.datetime.now(pytz.UTC),
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
		self.data.request = nts._dict(
			{
				"ip": nts.local.request_ip,
				"method": nts.request.method,
				"path": nts.request.path,
			}
		)

		if request_id := nts.request.headers.get("X-nts-Request-Id"):
			self.data.uuid = request_id

	def collect_job_meta(self, method, kwargs):
		self.data.job = nts._dict({"method": method, "scheduled": False, "wait": 0})
		if "run_scheduled_job" in method:
			self.data.job.method = kwargs["job_type"]
			self.data.job.scheduled = True

		if job := rq.get_current_job():
			self.data.job_id = job.id
			waitdiff = self.data.timestamp - job.enqueued_at.replace(tzinfo=pytz.UTC)
			self.data.job.wait = int(waitdiff.total_seconds() * 1000000)

	def add_custom_data(self, **kwargs):
		if self.data:
			self.data.update(kwargs)

	def dump(self, response=None):
		try:
			timediff = datetime.datetime.now(pytz.UTC) - self.data.timestamp
			# Obtain duration in microseconds
			self.data.duration = int(timediff.total_seconds() * 1000000)

			if self.data.transaction_type == "request":
				if response:
					self.data.request.status_code = response.status_code
					self.data.request.response_length = int(response.headers.get("Content-Length", 0))
				else:
					self.data.request.status_code = 500

				if hasattr(nts.local, "rate_limiter"):
					limiter = nts.local.rate_limiter
					self.data.request.counter = limiter.counter
					if limiter.rejected:
						self.data.request.reset = limiter.reset

			self.store()
		except Exception:
			traceback.print_exc()

	def store(self):
		serialized = json.dumps(self.data, sort_keys=True, default=str, separators=(",", ":"))
		length = nts.cache.rpush(MONITOR_REDIS_KEY, serialized)
		if cint(length) > MONITOR_MAX_ENTRIES:
			nts.cache.ltrim(MONITOR_REDIS_KEY, 1, -1)


def flush():
	logs = nts.cache.lrange(MONITOR_REDIS_KEY, 0, -1)
	if not logs:
		return

	logs = list(map(nts.safe_decode, logs))
	with filelock("monitor_flush", is_global=True, timeout=5):
		with open(log_file(), "a") as f:
			f.write("\n".join(logs))
			f.write("\n")

	# Remove fetched entries from cache
	nts.cache.ltrim(MONITOR_REDIS_KEY, len(logs) - 1, -1)
