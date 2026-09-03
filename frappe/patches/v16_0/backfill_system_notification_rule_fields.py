import frappe


def execute():
	"""Backfill subject and notification_type on System Notification rules."""
	frappe.reload_doctype("Notification")

	notification = frappe.qb.DocType("Notification")

	def _empty(col):
		return col.isnull() | (col == "")

	is_system_notification = notification.channel == "System Notification"

	if frappe.db.has_column("Notification", "notification_title"):
		frappe.qb.update(notification).set(notification.subject, notification.notification_title).where(
			is_system_notification & _empty(notification.subject) & ~_empty(notification.notification_title)
		).run()

	frappe.qb.update(notification).set(notification.notification_type, "Alert").where(
		is_system_notification & _empty(notification.notification_type)
	).run()
