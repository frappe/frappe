from __future__ import unicode_literals
import frappe, json

def execute():
	frappe.clear_cache()
	installed = frappe.get_installed_apps()
	if "webnotes" in installed:
		installed.remove("webnotes")
	if "frappe" not in installed:
		installed = ["frappe"] + installed
	frappe.db.set_global("installed_apps", json.dumps(installed))
	frappe.clear_cache()
