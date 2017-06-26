# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe, os
from frappe.model.document import Document

class TestRunner(Document):
	pass

@frappe.whitelist()
def get_all_tests():
	tests = []
	for app in frappe.get_installed_apps():
		tests_path = frappe.get_app_path(app, 'public', 'js', 'tests')
		if os.path.exists(tests_path):
			for fname in os.listdir(tests_path):
				if fname.startswith('test') and fname.endswith('.js'):
					tests.append('assets/{app}/js/tests/{fname}'.format(app=app,
						fname=fname))

	return tests
