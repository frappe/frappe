import json

import frappe


def execute():
	if frappe.db.exists("Social Login Key", "github"):
		frappe.db.set_value(
			"Social Login Key", "github", "auth_url_data", json.dumps({"scope": "user:email"})
		)
