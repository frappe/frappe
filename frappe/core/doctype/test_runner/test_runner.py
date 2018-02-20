# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, os
from frappe.model.document import Document

class TestRunner(Document):
	pass

@frappe.whitelist()
def get_test_js(test_path=None):
	'''Get test + data for app, example: app/tests/ui/test_name.js'''
	if not test_path:
		test_path = frappe.db.get_single_value('Test Runner', 'module_path')
	test_js = []

	# split
	app, test_path = test_path.split(os.path.sep, 1)

	# now full path
	test_path = frappe.get_app_path(app, test_path)

	def add_file(path):
		with open(path, 'r') as fileobj:
			test_js.append(dict(
				script = fileobj.read()
			))

	# add test_lib.js
	add_file(frappe.get_app_path('frappe', 'tests', 'ui', 'data', 'test_lib.js'))
	add_file(test_path)

	return test_js

