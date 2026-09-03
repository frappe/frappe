import frappe


def execute():
	"""Backfill notification_title and notification_type on System Notification rules."""
	frappe.reload_doctype("Notification")

	notification = frappe.qb.DocType("Notification")

	def _empty(col):
		return col.isnull() | (col == "")

	is_system_notification = notification.channel == "System Notification"

	frappe.qb.update(notification).set(notification.notification_title, notification.subject).where(
		is_system_notification & _empty(notification.notification_title) & ~_empty(notification.subject)
	).run()

	frappe.qb.update(notification).set(notification.notification_type, "Alert").where(
		is_system_notification & _empty(notification.notification_type)
	).run()
