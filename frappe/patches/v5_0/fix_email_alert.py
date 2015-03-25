from __future__ import unicode_literals

import frappe

def execute():
	frappe.reload_doctype("Email Alert")
	for e in frappe.get_all("Email Alert"):
		email_alert = frappe.get_doc("Email Alert", e.name)
		if email_alert.event == "Date Change":
			if email_alert.days_in_advance < 0:
				email_alert.event = "Days After"
				email_alert.days_in_advance = -email_alert.days_in_advance
			else:
				email_alert.event = "Days Before"

			email_alert.save()
