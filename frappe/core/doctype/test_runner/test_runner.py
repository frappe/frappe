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
		tests_path = frappe.get_app_path(app, 'tests', 'ui')
		if os.path.exists(tests_path):
			for basepath, folders, files in os.walk(tests_path): # pylint: disable=unused-variable
				for fname in files:
					if fname.startswith('test') and fname.endswith('.js'):
						path = os.path.join(basepath, fname)
						with open(path, 'r') as fileobj:
							tests.append(dict(
								path = os.path.relpath(frappe.get_app_path(app), path),
								script = fileobj.read()
							))
	return tests
