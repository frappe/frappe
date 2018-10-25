# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
import redis

def get_context(context):
	pass


@frappe.whitelist()
def get_paths():
	paths = frappe.cache().zrange("recorder-paths", 0, -1, desc=True)
	counts = super(redis.Redis, frappe.cache()).hgetall(frappe.cache().make_key("recorder-paths-counts"))

	paths = [{"path": path.decode(), "count": int(counts[path])} for path in paths]
	return paths

@frappe.whitelist()
def get_requests(path):
	requests = frappe.cache().lrange("recorder-requests-{}".format(path), 0, -1)
	requests = list(map(lambda request: request.decode(), requests))
	return [{"uuid": request} for request in requests]

@frappe.whitelist()
def get_calls(uuid):
	calls = frappe.cache().get("recorder-calls-{}".format(uuid))
	calls = json.loads(calls.decode())
	for index, call in enumerate(calls):
		call["index"] = index
	return calls
