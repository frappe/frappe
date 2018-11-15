from __future__ import unicode_literals
import frappe
from frappe.utils.verified_command import verify_request
from frappe.email.doctype.newsletter.newsletter import confirmed_unsubscribe

def get_context(context):
	frappe.flags.ignore_permissions=True
	if "email" in frappe.form_dict:
		if verify_request():
			user_email = frappe.form_dict["email"]
			context.email = user_email
			tittle = frappe.form_dict["name"]
			context.email_groups = get_email_groups(user_email)
			context.current_group = get_current_groups(tittle)
			context.status = "confirmation page"

	elif "user_email" in frappe.form_dict:
		context.status = "Unsubscribed page"
		email = frappe.form_dict['user_email']
		email_group = get_email_groups(email)
		for group in email_group:
			if group.email_group in frappe.form_dict:
				confirmed_unsubscribe(email, group.email_group)

	else:
		context.status = "not valid"

def get_email_groups(user_email):
	return frappe.get_all("Email Group Member", fields = ["email_group"], filters = {"email": user_email, "unsubscribed": 0}, ignore_permissions=True )

def get_current_groups(name):
	return frappe.db.get_all("Newsletter Email Group", ["email_group"],{"parent":name, "parenttype":"Newsletter"}, ignore_permissions=True)