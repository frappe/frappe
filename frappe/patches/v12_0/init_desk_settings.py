from __future__ import unicode_literals

import json
import frappe
from frappe.config import get_modules_from_all_apps_for_user
from frappe.desk.moduleview import get_onboard_items

def execute():
	"""Set the initial customizations for desk, with modules, indices and links."""
	frappe.reload_doc("core", "doctype", "user")
	all_modules = get_modules_from_all_apps_for_user()

	settings = {}

	for module in all_modules:
		if not module.get("app"): continue

		links = get_onboard_items(module["app"], frappe.scrub(module["module_name"]))[:5]
		module_settings = {
			"links": ",".join([d["label"] for d in links])
		}
		category_dict = settings.get(module.get("category", ""), None)
		if category_dict:
			module_settings["index"] = len(category_dict)
			category_dict[module.get("module_name")] = module_settings
		else:
			module_settings["index"] = 0
			settings[module.get("category", "")] = {
				module.get("module_name"): module_settings
			}

	settings_json_str = json.dumps(settings)

	frappe.db.sql("""update tabUser set home_settings = %s""", (settings_json_str), debug=True)
