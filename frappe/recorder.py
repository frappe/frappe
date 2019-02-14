# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import json
import time
import traceback
import frappe
import sqlparse
import uuid
import datetime

from pygments import highlight
from pygments.lexers import MySqlLexer
from pygments.formatters import HtmlFormatter

def sql(*args, **kwargs):
	# Execute wrapped function as is
	# Record arguments as well as return value
	# Record start and end time as well
	start_time = time.time()
	result = frappe.db._sql(*args, **kwargs)
	end_time = time.time()

	stack = "".join(traceback.format_stack())

	# Big hack here
	# PyMysql stores exact DB query in cursor._executed
	# Assumes that function refers to frappe.db.sql
	# __self__ will refer to frappe.db
	# Rest is trivial
	query = frappe.db._cursor._executed
	compressed_result = compress(result)

	# Built in profiler is already turned on
	# Now fetch the profile data for last query
	# This must be done after collecting query from _cursor._executed
	profile_result = frappe.db._sql("SHOW PROFILE", as_dict=True)

	# Collect EXPLAIN for executed query
	if query.lower().strip().split()[0] in ("select", "update", "delete"):
		# Only SELECT/UPDATE/DELETE queries can be "EXPLAIN"ed
		explain_result = frappe.db._sql("EXPLAIN EXTENDED {}".format(query), as_dict=True)
	else:
		explain_result = ""

	query = sqlparse.format(query.strip(), keyword_case="upper", reindent=True)
	data = {
		"result": compressed_result,
		"query": query,
		"highlighted_query": highlight(query, MySqlLexer(), HtmlFormatter()),
		"explain_result": compress(explain_result),
		"profile_result": compress(profile_result),
		"stack": stack,
		"time": start_time,
		"duration": float("{:.3f}".format((end_time - start_time) * 1000)),
	}

	# Record all calls, Will be later stored in cache
	frappe.local._recorder.register(data)
	return result


def record():
	if frappe.cache().get("recorder-intercept"):
		frappe.local._recorder = Recorder()


def dump():
	if hasattr(frappe.local, "_recorder"):
		frappe.local._recorder.dump()
		frappe.publish_realtime(event="recorder-dump-event")


class Recorder():
	def __init__(self):
		self.uuid = frappe.generate_hash(length=10)
		self.time = datetime.datetime.now()
		self.calls = []
		self.path = frappe.request.path
		self.cmd = frappe.local.form_dict.cmd or ""
		self.method = frappe.request.method

		self.request = {
			"headers": dict(frappe.local.request.headers),
			"data": frappe.local.form_dict,
		}
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
			"duration": float("{:0.3f}".format((datetime.datetime.now() - self.time).total_seconds() * 1000)),
			"method": self.method,
		}
		frappe.cache().lpush("recorder-requests", json.dumps(request_data, default=str))

		request_data["calls"] = self.calls
		request_data["http"] = self.request
		frappe.cache().set("recorder-request-{}".format(self.uuid), json.dumps(request_data, default=str))


def _patch():
	frappe.db._sql = frappe.db.sql
	frappe.db.sql = sql
	frappe.db._sql("SET PROFILING = 1")


def compress(data):
	if data:
		if isinstance(data[0], dict):
			keys = list(data[0].keys())
			values = list()
			for row in data:
				values.append([row.get(key) for key in keys])
		else:
			keys = [column[0] for column in frappe.db._cursor.description]
			values = data
	else:
		keys, values = [], []
	return {"keys": keys, "values": values}
