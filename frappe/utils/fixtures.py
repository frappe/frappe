# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe, os
from frappe.core.page.data_import_tool.data_import_tool import import_doc, export_json

def sync_fixtures(app=None):
	"""Import, overwrite fixtures from `[app]/fixtures`"""
	if app:
		apps = [app]
	else:
		apps = frappe.get_installed_apps()
	for app in apps:
		if os.path.exists(frappe.get_app_path(app, "fixtures")):
			for fname in os.listdir(frappe.get_app_path(app, "fixtures")):
				if fname.endswith(".json") or fname.endswith(".csv"):
					import_doc(frappe.get_app_path(app, "fixtures", fname), ignore_links=True, overwrite=True)

		import_custom_scripts(app)

	frappe.db.commit()

def import_custom_scripts(app):
	"""Import custom scripts from `[app]/fixtures/custom_scripts`"""
	if os.path.exists(frappe.get_app_path(app, "fixtures", "custom_scripts")):
		for fname in os.listdir(frappe.get_app_path(app, "fixtures", "custom_scripts")):
			if fname.endswith(".js"):
				with open(frappe.get_app_path(app, "fixtures",
					"custom_scripts") + os.path.sep + fname) as f:
					doctype = fname.rsplit(".", 1)[0]
					script = f.read()
					if frappe.db.exists("Custom Script", {"dt": doctype}):
						custom_script = frappe.get_doc("Custom Script", {"dt": doctype})
						custom_script.script = script
						custom_script.save()
					else:
						frappe.get_doc({
							"doctype":"Custom Script",
							"dt": doctype,
							"script_type": "Client",
							"script": script
						}).insert()

def export_fixtures():
	"""Export fixtures as JSON to `[app]/fixtures`"""
	for app in frappe.get_installed_apps():
		for fixture in frappe.get_hooks("fixtures", app_name=app):
			filters = None
			if isinstance(fixture, dict):
				filters = fixture.get("filters")
				fixture = fixture.get("doctype") or fixture.get("dt")
			print "Exporting {0} app {1} filters {2}".format(fixture, app, filters)
			if not os.path.exists(frappe.get_app_path(app, "fixtures")):
				os.mkdir(frappe.get_app_path(app, "fixtures"))

			export_json(fixture, frappe.get_app_path(app, "fixtures", frappe.scrub(fixture) + ".json"), filters=filters)
