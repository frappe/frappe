from __future__ import unicode_literals

import frappe

def execute():
	frappe.reload_doctype("Notification")
	for e in frappe.get_all("Notification"):
		notification = frappe.get_doc("Notification", e.name)
		if notification.event == "Date Change":
			if notification.days_in_advance < 0:
				notification.event = "Days After"
				notification.days_in_advance = -email_alert.days_in_advance
			else:
				notification.event = "Days Before"

			notification.save()
