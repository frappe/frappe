import frappe
from frappe.doctypes import EmailUnsubscribe


def execute():
	email_unsubscribe = [
		{"email": "admin@example.com", "global_unsubscribe": 1},
		{"email": "guest@example.com", "global_unsubscribe": 1},
	]

	for unsubscribe in email_unsubscribe:
		if not frappe.get_all("Email Unsubscribe", filters=unsubscribe):
			doc = EmailUnsubscribe.docs.new()
			doc.update(unsubscribe)
			doc.insert(ignore_permissions=True)
