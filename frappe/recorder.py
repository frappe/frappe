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

	# Built in profiler is already turned on
	# Now fetch the profile data for last query
	# This must be done after collecting query from _cursor._executed
	profile_result = frappe.db._sql("SHOW PROFILE ALL", as_dict=True)

	# Collect EXPLAIN for executed query
	if query.lower().strip().split()[0] in ("select", "update", "delete"):
		# Only SELECT/UPDATE/DELETE queries can be "EXPLAIN"ed
		explain_result = frappe.db._sql("EXPLAIN EXTENDED {}".format(query), as_dict=True)
	else:
		explain_result = ""

	data = {
		"args": args,
		"kwargs": kwargs,
		"result": result,
		"query": sqlparse.format(query, keyword_case="upper", reindent=True),
		"explain_result": explain_result,
		"profile_result": profile_result,
		"stack": stack,
		"time": {
			"start": start_time,
			"end": end_time,
			"total": end_time - start_time,
		},
	}

	# Record all calls, Will be later stored in cache
	frappe.local._recorder.register(data)
	return result


def record():
	frappe.local._recorder = Recorder()


def dump():
	frappe.local._recorder.dump()


class Recorder():
	def __init__(self):
		self.uuid = str(uuid.uuid1())
		self.time = datetime.datetime.now()
		self.calls = []
		self.path = frappe.request.path
		self.cmd = frappe.local.form_dict.cmd
		self.method = frappe.request.method

		self._patch()

	def register(self, data):
		self.calls.append(data)

	def dump(self):
		frappe.cache().lpush(
			"recorder-requests",
			json.dumps({
				"uuid": self.uuid,
				"path": self.path,
				"cmd": self.cmd,
				"time": self.time,
				"method": self.method,
			}, default=lambda x: str(x))
		)
		frappe.cache().set(
			"recorder-request-{}".format(self.uuid),
			json.dumps(self.calls, default=lambda x: str(x))
		)

	def _patch(self):
		frappe.db._sql = frappe.db.sql
		frappe.db.sql = sql
