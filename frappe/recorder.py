# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import datetime
import functools
import inspect
import json
import re
import time
from collections import Counter
from typing import Callable

import sqlparse

import frappe
from frappe import _
from frappe.database.database import is_query_type

RECORDER_INTERCEPT_FLAG = "recorder-intercept"
RECORDER_REQUEST_SPARSE_HASH = "recorder-requests-sparse"
RECORDER_REQUEST_HASH = "recorder-requests"
TRACEBACK_PATH_PATTERN = re.compile(".*/apps/")


def sql(*args, **kwargs):
	start_time = time.time()
	result = frappe.db._sql(*args, **kwargs)
	end_time = time.time()

	stack = list(get_current_stack_frames())

	data = {
		"query": str(frappe.db.last_query),
		"stack": stack,
		"explain_result": [],
		"time": start_time,
		"duration": float(f"{(end_time - start_time) * 1000:.3f}"),
	}

	frappe.local._recorder.register(data)
	return result


def get_current_stack_frames():
	try:
		current = inspect.currentframe()
		frames = inspect.getouterframes(current, context=10)
		for frame, filename, lineno, function, context, index in list(reversed(frames))[:-2]:
			if "/apps/" in filename or "<serverscript>" in filename:
				yield {
					"filename": TRACEBACK_PATH_PATTERN.sub("", filename),
					"lineno": lineno,
					"function": function,
				}
	except Exception:
		pass


def post_process():
	"""post process all recorded values.

	Any processing that can be done later should be done here to avoid overhead while
	profiling. As of now following values are post-processed:
	        - `EXPLAIN` output of queries.
	        - SQLParse reformatting of queries
	        - Mark duplicates
	"""
	frappe.db.rollback()
	frappe.db.begin(read_only=True)  # Explicitly start read only transaction

	result = list(frappe.cache().hgetall(RECORDER_REQUEST_HASH).values())

	for request in result:
		for call in request["calls"]:
			formatted_query = sqlparse.format(call["query"].strip(), keyword_case="upper", reindent=True)
			call["query"] = formatted_query

			# Collect EXPLAIN for executed query
			if is_query_type(formatted_query, ("select", "update", "delete")):
				# Only SELECT/UPDATE/DELETE queries can be "EXPLAIN"ed
				try:
					call["explain_result"] = frappe.db.sql(f"EXPLAIN {formatted_query}", as_dict=True)
				except Exception:
					pass
		mark_duplicates(request)
		frappe.cache().hset(RECORDER_REQUEST_HASH, request["uuid"], request)


def mark_duplicates(request):
	exact_duplicates = Counter([call["query"] for call in request["calls"]])

	for sql_call in request["calls"]:
		sql_call["normalized_query"] = normalize_query(sql_call["query"])

	normalized_duplicates = Counter([call["normalized_query"] for call in request["calls"]])

	for index, call in enumerate(request["calls"]):
		call["index"] = index
		call["exact_copies"] = exact_duplicates[call["query"]]
		call["normalized_copies"] = normalized_duplicates[call["normalized_query"]]


def normalize_query(query: str) -> str:
	"""Attempt to normalize query by removing variables.
	This gives a different view of similar duplicate queries.

	Example:
	        These two are distinct queries:
	                `select * from user where name = 'x'`
	                `select * from user where name = 'z'`

	        But their "normalized" form would be same:
	                `select * from user where name = ?`
	"""

	try:
		q = sqlparse.parse(query)[0]
		for token in q.flatten():
			if "Token.Literal" in str(token.ttype):
				token.value = "?"
		return str(q)
	except Exception as e:
		print("Failed to normalize query ", e)

	return query


def record(force=False):
	if __debug__:
		if frappe.cache().get_value(RECORDER_INTERCEPT_FLAG) or force:
			frappe.local._recorder = Recorder()


def dump():
	if __debug__:
		if hasattr(frappe.local, "_recorder"):
			frappe.local._recorder.dump()


class Recorder:
	def __init__(self):
		self.uuid = frappe.generate_hash(length=10)
		self.time = datetime.datetime.now()
		self.calls = []
		if frappe.request:
			self.path = frappe.request.path
			self.cmd = frappe.local.form_dict.cmd or ""
			self.method = frappe.request.method
			self.headers = dict(frappe.local.request.headers)
			self.form_dict = frappe.local.form_dict
		else:
			self.path = None
			self.cmd = None
			self.method = None
			self.headers = None
			self.form_dict = None

		_patch()

	def register(self, data):
		self.calls.append(data)

	def dump(self):
		request_data = {
			"uuid": self.uuid,
			"path": self.path,
			"cmd": self.cmd,
			"time": self.time,
			"queries": len(self.calls),
			"time_queries": float("{:0.3f}".format(sum(call["duration"] for call in self.calls))),
			"duration": float(f"{(datetime.datetime.now() - self.time).total_seconds() * 1000:0.3f}"),
			"method": self.method,
		}
		frappe.cache().hset(RECORDER_REQUEST_SPARSE_HASH, self.uuid, request_data)
		frappe.publish_realtime(
			event="recorder-dump-event",
			message=json.dumps(request_data, default=str),
			user="Administrator",
		)

		request_data["calls"] = self.calls
		request_data["headers"] = self.headers
		request_data["form_dict"] = self.form_dict
		frappe.cache().hset(RECORDER_REQUEST_HASH, self.uuid, request_data)


def _patch():
	frappe.db._sql = frappe.db.sql
	frappe.db.sql = sql


def _unpatch():
	frappe.db.sql = frappe.db._sql


def do_not_record(function):
	def wrapper(*args, **kwargs):
		if hasattr(frappe.local, "_recorder"):
			del frappe.local._recorder
			frappe.db.sql = frappe.db._sql
		return function(*args, **kwargs)

	return wrapper


def administrator_only(function):
	def wrapper(*args, **kwargs):
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator is allowed to use Recorder"))
		return function(*args, **kwargs)

	return wrapper


@frappe.whitelist()
@do_not_record
@administrator_only
def status(*args, **kwargs):
	return bool(frappe.cache().get_value(RECORDER_INTERCEPT_FLAG))


@frappe.whitelist()
@do_not_record
@administrator_only
def start(*args, **kwargs):
	frappe.cache().set_value(RECORDER_INTERCEPT_FLAG, 1, expires_in_sec=60 * 60)


@frappe.whitelist()
@do_not_record
@administrator_only
def stop(*args, **kwargs):
	frappe.cache().delete_value(RECORDER_INTERCEPT_FLAG)
	frappe.enqueue(post_process)


@frappe.whitelist()
@do_not_record
@administrator_only
def get(uuid=None, *args, **kwargs):
	if uuid:
		result = frappe.cache().hget(RECORDER_REQUEST_HASH, uuid)
	else:
		result = list(frappe.cache().hgetall(RECORDER_REQUEST_SPARSE_HASH).values())
	return result


@frappe.whitelist()
@do_not_record
@administrator_only
def export_data(*args, **kwargs):
	return list(frappe.cache().hgetall(RECORDER_REQUEST_HASH).values())


@frappe.whitelist()
@do_not_record
@administrator_only
def delete(*args, **kwargs):
	frappe.cache().delete_value(RECORDER_REQUEST_SPARSE_HASH)
	frappe.cache().delete_value(RECORDER_REQUEST_HASH)


def record_queries(func: Callable):
	"""Decorator to profile a specific function using recorder."""

	@functools.wraps(func)
	def wrapped(*args, **kwargs):
		record(force=True)
		frappe.local._recorder.path = f"Function call: {func.__module__}.{func.__qualname__}"
		ret = func(*args, **kwargs)
		dump()
		_unpatch()
		post_process()
		print("Recorded queries, open recorder to view them.")
		return ret

	return wrapped
