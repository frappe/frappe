# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, os
from frappe.model.document import Document

class TestRunner(Document):
	pass

@frappe.whitelist()
def get_test_js():
	'''Get test + data for app, example: app/tests/ui/test_name.js'''
	test_path = frappe.db.get_single_value('Test Runner', 'module_path')

	# split
	app, test_path = test_path.split(os.path.sep, 1)
	test_js = get_test_data(app)

	# full path
	test_path = frappe.get_app_path(app, test_path)

	with open(test_path, 'r') as fileobj:
		test_js.append(dict(
			script = fileobj.read()
		))
	return test_js

def get_test_data(app):
	'''Get the test fixtures from all js files in app/tests/ui/data'''
	test_js = []

	def add_file(path):
		with open(path, 'r') as fileobj:
			test_js.append(dict(
				script = fileobj.read()
			))

	data_path = frappe.get_app_path(app, 'tests', 'ui', 'data')
	if os.path.exists(data_path):
		for fname in os.listdir(data_path):
			if fname.endswith('.js'):
				add_file(os.path.join(data_path, fname))

	if app != 'frappe':
		add_file(frappe.get_app_path('frappe', 'tests', 'ui', 'data', 'test_lib.js'))

	return test_js
