# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 

from __future__ import unicode_literals

import frappe, os
from frappe.core.page.data_import_tool.data_import_tool import import_doclist

def sync_fixtures():
	for app in frappe.get_installed_apps():
		if os.path.exists(frappe.get_app_path(app, "fixtures")):
			for fname in os.listdir(frappe.get_app_path(app, "fixtures")):
				if fname.endswith(".json") or fname.endswith(".csv"):
					import_doclist(frappe.get_app_path(app, "fixtures", fname))
