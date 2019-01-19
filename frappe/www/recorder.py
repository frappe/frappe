# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
import redis
from pygments.formatters import HtmlFormatter

def do_not_record():
	if hasattr(frappe.local, "_recorder"):
		del frappe.local._recorder
		frappe.db.sql = frappe.db._sql


def get_context(context):
	do_not_record()
	if frappe.request.path[-1] != "/":
		frappe.local.flags.redirect_location = "recorder/"
		raise frappe.Redirect
	return {"highlight": HtmlFormatter().get_style_defs()}

@frappe.whitelist()
def get_status():
	do_not_record()
	if frappe.cache().get("recorder-intercept"):
		return {"status": "Active", "color": "green"}
	return {"status": "Inactive", "color": "red"}


@frappe.whitelist()
def set_recorder_state(should_record):
	do_not_record()
	if should_record == "true":
		frappe.cache().set("recorder-intercept", 1)
		return {"status": "Active", "color": "green"}
	else:
		frappe.cache().delete("recorder-intercept")
		return {"status": "Inactive", "color": "red"}


@frappe.whitelist()
def get_requests():
	do_not_record()
	requests = frappe.cache().lrange("recorder-requests", 0, -1)
	requests = list(map(lambda request: json.loads(request.decode()), requests))
	for index, request in enumerate(requests, start=1):
		request["index"] = index
	return requests


@frappe.whitelist()
def get_request_data(uuid):
	do_not_record()
	calls = frappe.cache().get("recorder-request-{}".format(uuid))
	calls = json.loads(calls.decode())
	for index, call in enumerate(calls):
		call["index"] = index

	return {
		"calls": calls,
	}

