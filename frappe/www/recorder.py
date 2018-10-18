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
