from __future__ import unicode_literals

import frappe
from frappe.desk.doctype.notification_settings.notification_settings import (
	create_notification_settings,
)


def execute():
	frappe.reload_doc("desk", "doctype", "notification_settings")
	frappe.reload_doc("desk", "doctype", "notification_subscribed_document")

	users = frappe.db.get_all("User", fields=["name"])
	for user in users:
		create_notification_settings(user.name)
