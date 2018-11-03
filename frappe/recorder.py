# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import json
import time
import frappe

def time_ms():
	return time.time() * 1000

def wrap_cache():
	def cache_recorder(function):
		def wrapper(*args, **kwargs):
			start_time_ms = time_ms()
			result = function(*args, **kwargs)
			end_time_ms = time_ms()

			import traceback
			# Some elementary analysis shows that following lines are a little time consuming
			# These can be made optional.
			stack = "".join(traceback.format_stack())

			data = {
				"function": function.__name__,
				#"args": args,
				#"kwargs": kwargs,
				# result is sometimes a nested dict, those can't be sometimes JSON serialized.
				# pickle.dumps seems like a nice way to go., but JS can't understand pickle.
				# Skip result for now
				# "result": result,
				"stack": stack,
				# Exact redis query is not available for now
				# Regenerate equivalent function call instead.
				"call": "{}(*{},**{})".format(function.__name__, args, kwargs),
				"time": {
					"start": start_time_ms,
					"end": end_time_ms,
					"total": end_time_ms - start_time_ms,
				},
			}

			wrapper.calls.append(data)
			return result
		wrapper.calls = list()
		return wrapper

	# frappe.cache() will provide an instance of RedisWrapper
	# Selected methods of this class are used to do cache operations
	# Recording activity of these methods will give a nice picture of cache activity

	# cache_methods lists all interesting cache methods
	# Override these methods with the use of wrapper function
	# that records each call along with some suplimentary data
	redis_server = frappe.cache()
	cache_methods = [
		"set_value", "get_value",
		"get_all", "get_keys",
		"delete_keys", "delete_key", "delete_value",
		"lpush", "rpush", "lpop", "llen", "lrange",
		"hset", "hgetall", "hincrby", "hget", "hdel", "hdel_keys", "hkeys",
		"sadd", "srem", "sismember", "spop", "srandmember", "smembers",
		"zincrby", "zrange"
	]

	# cache_methods will be needed again while storing recorded calls in cache
	# Store cache_methods list in cache_methods attribute of wrap_cache
	wrap_cache.cache_methods = cache_methods
	for method in cache_methods:
		# For now assume that all these methods exist on RedisWrapper instance
		original = getattr(redis_server, method)
		modified = cache_recorder(original)
		setattr(redis_server, method, modified)

def persist_cache():
	redis_server = frappe.cache()
	cache_methods = wrap_cache.cache_methods
	calls = []
	uuid = frappe.request.environ["uuid"]
	for method in cache_methods:
		# Assumes that the method exists on RedisWrapper instance
		# and function.calls also exists
		function = getattr(redis_server, method)
		calls.extend(function.calls)

	# Record all calls in cache
	frappe.cache().set("recorder-calls-cache-{}".format(uuid), dumps(calls))

def recorder(function):
	def wrapper(*args, **kwargs):
		# Execute wrapped function as is
		# Record arguments as well as return value
		# Record start and end time as well
		start_time_ms = time_ms()
		result = function(*args, **kwargs)
		end_time_ms = time_ms()

		import traceback
		stack = "".join(traceback.format_stack())

		# Big hack here
		# PyMysql stores exact DB query in cursor._executed
		# Assumes that function refers to frappe.db.sql
		# __self__ will refer to frappe.db
		# Rest is trivial
		query = function.__self__._cursor._executed
		data = {
			"function": function.__name__,
			"args": args,
			"kwargs": kwargs,
			"result": result,
			"query": query,
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
	frappe.cache().lpush("recorder-requests-{}".format(path), uuid)

	# LPUSH -> Chronological order for calls
	# Since every request uuid is unique, no need for any heirarchy

	# Datetime objects cannot be used with json.dumps
	# str() seems to work with them
	frappe.cache().set("recorder-calls-{}".format(uuid), dumps(calls))
