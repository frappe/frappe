import frappe


def execute():
	doctype = "Integration Request"
	frappe.db.set_value(
		doctype,
		{"integration_type": "Remote", "integration_request_service": ("!=", "PayPal")},
		"is_remote_request",
		1,
	)
	frappe.db.set_value(
		doctype,
		{"integration_type": "Subscription Notification"},
		"request_description",
		"Subscription Notification",
	)
