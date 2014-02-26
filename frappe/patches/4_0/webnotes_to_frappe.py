import frappe, json

def execute():
	installed = frappe.get_installed_apps()
	if "webnotes" in installed:
		installed.remove("webnotes")
	installed = ["frappe"] + installed
	frappe.db.set_global("installed_apps", json.dumps(installed))
	frappe.clear_cache()