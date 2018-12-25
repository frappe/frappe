# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import json
import time
import traceback
import frappe
import sqlparse

def recorder_start():
		# Need to record all calls to frappe.db.sql
		# Should be done after frappe.db refers to an instance of Database
		# Now is a good time
		# If uuid is not set then RecorderMiddleware isn't active
		if "uuid" in frappe.request.environ:
			frappe.db.sql = recorder(frappe.db.sql)

def recorder_stop():
		# Recorded calls need to be stored in cache
		# This looks like a terribe syntax, Because it actually is
		if "uuid" in frappe.request.environ:
			persist(frappe.db.sql)

def time_ms():
	return time.time() * 1000


def recorder(function):
	def wrapper(*args, **kwargs):
		# Execute wrapped function as is
		# Record arguments as well as return value
		# Record start and end time as well
		start_time_ms = time_ms()
		result = function(*args, **kwargs)
		end_time_ms = time_ms()

		stack = "".join(traceback.format_stack())

		# Big hack here
		# PyMysql stores exact DB query in cursor._executed
		# Assumes that function refers to frappe.db.sql
		# __self__ will refer to frappe.db
		# Rest is trivial
		query = function.__self__._cursor._executed

		# Built in profiler is already turned on
		# Now fetch the profile data for last query
		# This must be done after collecting query from _cursor._executed
		profile_result = function("SHOW PROFILE ALL", as_dict=True)

		# Collect EXPLAIN for executed query
		if query.lower().strip().split()[0] in ("select", "update", "delete"):
			# Only SELECT/UPDATE/DELETE queries can be "EXPLAIN"ed
			explain_result = function("EXPLAIN EXTENDED {}".format(query), as_dict=True)
		else:
			explain_result = ""

		data = {
			"function": function.__name__,
			"args": args,
			"kwargs": kwargs,
			"result": result,
			"query": sqlparse.format(query, keyword_case="upper", reindent=True),
			"explain_result": explain_result,
			"profile_result": profile_result,
			"stack": stack,
			"time": {
				"start": start_time_ms,
				"end": end_time_ms,
				"total": end_time_ms - start_time_ms,
			},
		}

		# Record all calls, Will be later stored in cache
		wrapper.calls.append(data)
		return result

	wrapper.calls = list()
	wrapper.path = frappe.request.path
	wrapper.cmd = frappe.local.form_dict.cmd

	# Enable MariaDB's builtin query profiler.
	# Profile data can be collected after each query.
	function("SET profiling = 1")
	return wrapper

def dumps(stuff):
	return json.dumps(stuff, default=lambda x: str(x))

def persist(function):
	"""Stores recorded requests and calls in redis cache with following hierarchy

	recorder-paths -> ["Path1", "Path2", ... ,"Path3"]

	recorder-paths is a sorted set, Paths have non decreasing score,
	Highest score means recently visited

	recorder-requests-[path] -> ["UUID3", "UUID2", ...]
	recorder-requests-[path] is a list of UUIDs of requests made on that path
	in reverse chronological order

	recorder-requests-[uuid] -> ["Call1", "Call2"]
	recorder-requests-[uuid] is a list of calls made during that request
	in chronological order
	"""
	path = function.path
	cmd = function.cmd
	calls = function.calls

	# RecorderMiddleware creates a uuid for every request and
	# stores it in request environ
	uuid = frappe.request.environ["uuid"]

	# Redis Sorted Set -> Ordered set (Ordereed by `score`)
	# Elements are ordered from low to high score

	# Get the highest score from our set
	highest_score = frappe.cache().zrange("recorder-paths", -1, -1, withscores=True)

	# In the begning we might not even have a highest score
	# We have to start somewhere, 0 seems like a safe bet
	highest_score = highest_score[0][1] if highest_score else 0

	# Now insert `path` with score highest + 1
	# Effectively giving `path` the highest score
	# Note: Iff these two operations are done consequtively
	# Note: score can grow exponentially, Will probably need a fix
	frappe.cache().zincrby("recorder-paths", path, amount=float(highest_score)+1)

	# Also record number of times each URL was hit
	frappe.cache().hincrby("recorder-paths-counts", path, 1)

	# LPUSH -> Reverse chronological order for requests
	frappe.cache().lpush("recorder-requests-{}".format(path), json.dumps({"uuid": uuid, "cmd": cmd}))

	# LPUSH -> Chronological order for calls
	# Since every request uuid is unique, no need for any heirarchy

	# Datetime objects cannot be used with json.dumps
	# str() seems to work with them
	frappe.cache().set("recorder-calls-{}".format(uuid), dumps(calls))
