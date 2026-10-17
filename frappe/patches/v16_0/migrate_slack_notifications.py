import frappe
from frappe.model.utils.rename_field import (
	update_property_setters,
	update_reports,
	update_user_settings,
	update_users_report_view_settings,
)


def execute():
	frappe.db.set_value(
		"Notification Webhook URL", {"service": ["is", "not set"]}, "service", "Slack", update_modified=False
	)
	if frappe.db.has_column("Notification", "slack_webhook_url"):
		migrate_notification_links()

	frappe.db.set_value("Notification", {"channel": "Slack"}, "channel", "Webhook", update_modified=False)
	frappe.clear_cache(doctype="Notification")


def migrate_notification_links():
	"""Copy legacy targets without overwriting an already migrated notification."""
	Notification = frappe.qb.DocType("Notification")
	query = (
		frappe.qb.update(Notification)
		.set(Notification.notification_webhook_url, Notification.slack_webhook_url)
		.where(Notification.channel == "Slack")
		.where(Notification.notification_webhook_url.isnull() | (Notification.notification_webhook_url == ""))
	)
	query.run()

	for update in (
		update_reports,
		update_users_report_view_settings,
		update_property_setters,
		update_user_settings,
	):
		update("Notification", "slack_webhook_url", "notification_webhook_url")
