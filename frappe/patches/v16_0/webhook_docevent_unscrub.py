import frappe


def execute():
	webhooks = frappe.get_all("Webhook", ["name", "webhook_docevent"])
	for webhook in webhooks:
		frappe.db.set_value(
			"Webhook", webhook.name, "webhook_docevent", frappe.unscrub(webhook.webhook_docevent)
		)
