import frappe
import json

def execute():
	if frappe.db.exists("Social Login Key", "github"):
		frappe.db.set_value("Social Login Key", "github", "api_endpoint", "user/emails")
		frappe.db.set_value("Social Login Key", "github", "auth_url_data",
			json.dumps({
				"scope": "user:email"
			})
		)
