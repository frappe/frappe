import frappe


def execute():
	if frappe.db.exists("DocType", "Slack Webhook URL"):
		frappe.rename_doc("DocType", "Slack Webhook URL", "Notification Webhook URL")
