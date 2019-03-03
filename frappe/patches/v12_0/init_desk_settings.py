from __future__ import unicode_literals

import frappe
import json
from frappe.config import get_modules_from_all_apps_for_user

def execute():
	frappe.reload_doc("core", "doctype", "user")
	all_modules = get_modules_from_all_apps_for_user()

	settings = {}

	for idx, m in enumerate(all_modules):
		module_settings = {
			"links": ",".join([d["label"] for d in m.get("shortcuts")])
		}
		category_dict = settings.get(m.get("category", ""), None)
		if category_dict:
			module_settings["index"] = len(category_dict)
			category_dict[m.get("module_name")] = module_settings
		else:
			module_settings["index"] = 0
			settings[m.get("category", "")] = {
				m.get("module_name"): module_settings
			}

	settings_json_str = json.dumps(settings)

	frappe.db.sql("""update tabUser set home_settings = %s""", (settings_json_str), debug=True)
