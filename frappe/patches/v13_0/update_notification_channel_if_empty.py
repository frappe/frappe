# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def execute():
	frappe.reload_doc("Email", "doctype", "Notification")

	notifications = frappe.get_all("Notification", {"is_standard": 1}, {"name", "channel"})
	for notification in notifications:
		if not notification.channel:
			frappe.db.set_value("Notification", notification.name, "channel", "Email", update_modified=False)
			frappe.db.commit()
