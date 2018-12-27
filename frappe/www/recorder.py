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
def get_requests():
	requests = frappe.cache().lrange("recorder-requests", 0, -1)
	requests = list(map(lambda request: json.loads(request.decode()), requests))
	return requests


@frappe.whitelist()
def get_request_data(uuid):
	calls = frappe.cache().get("recorder-request-{}".format(uuid))
	calls = json.loads(calls.decode())
	for index, call in enumerate(calls):
		call["index"] = index

	return {
		"calls": calls,
	}

