import json

import frappe


def execute() -> None:
	if frappe.db.exists("Social Login Key", "github"):
		frappe.db.set_value(
			"Social Login Key", "github", "auth_url_data", json.dumps({"scope": "user:email"})
		)
