from __future__ import unicode_literals
import frappe
from frappe.email.doctype.newsletter.newsletter import confirmed_unsubscribe

def get_context(context):
		if "user_email" in frappe.form_dict:
			email = frappe.form_dict['user_email']
			email_group = get_email_groups(email)
			print("---------------------------------GROUP------------------------------------------------")
			print(email_group)
			print(frappe.form_dict)
			for group in email_group:
					print("hello---------------------------")
					if group.email_group in frappe.form_dict:
						confirmed_unsubscribe(email, group.email_group)

def get_email_groups(user_email):
	return frappe.get_all("Email Group Member", fields = ["email_group"], filters = {"email": user_email})