import frappe


def execute():
	frappe.db.set_value(
		"System Settings",
		"System Settings",
		{"document_share_key_expiry": 30, "allow_older_web_view_links": 1},
	)
