# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json

def get_context(context):
	result = frappe.cache().lrange("recorder-sql", 0, -1)
	result = [json.loads(line.decode()) for line in result]
	paths = {}
	for line in result:
		paths.setdefault(line["path"], []).append(line)
	return {"result": paths}


@frappe.whitelist()
def get_paths():
	paths = frappe.cache().zrange("recorder-paths", 0, -1, desc=True)
	paths = list(map(lambda path: path.decode(), paths))
	return paths

@frappe.whitelist()
def get_requests(path):
	requests = frappe.cache().lrange("recorder-requests-{}".format(path), 0, -1)
	requests = list(map(lambda request: request.decode(), requests))
	return requests

@frappe.whitelist()
def get_calls(uuid):
	calls = frappe.cache().lrange("recorder-calls-{}".format(uuid), 0, -1)
	calls = list(map(lambda call: call.decode(), calls))
	return calls
