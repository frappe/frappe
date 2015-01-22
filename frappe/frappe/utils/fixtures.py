# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe, os
from frappe.core.page.data_import_tool.data_import_tool import import_doc, export_fixture, export_csv

def sync_fixtures(app=None):
	if app:
		apps = [app]
	else:
		apps = frappe.get_installed_apps()
	for app in apps:
		if os.path.exists(frappe.get_app_path(app, "fixtures")):
			for fname in os.listdir(frappe.get_app_path(app, "fixtures")):
				if fname.endswith(".json") or fname.endswith(".csv"):
					import_doc(frappe.get_app_path(app, "fixtures", fname), ignore_links=True, overwrite=True)

	frappe.db.commit()

def export_fixtures():
	for app in frappe.get_installed_apps():
		for fixture in frappe.get_hooks("fixtures", app_name=app):
			print "Exporting {0}".format(fixture)
			if not os.path.exists(frappe.get_app_path(app, "fixtures")):
				os.mkdir(frappe.get_app_path(app, "fixtures"))
			if isinstance(fixture, basestring):
				fixture = [fixture];
			if frappe.db.get_value("DocType", fixture[0], "issingle"):
				export_fixture(fixture[0], fixture[0], app)
			else:
				export_csv(fixture, frappe.get_app_path(app, "fixtures", frappe.scrub(fixture[0]) + ".csv"))
