from __future__ import unicode_literals
import frappe


def get_context(context):
		if '_signature' in frappe.form_dict:
			user_email = frappe.form_dict["email"]
			context.email = user_email
			tittle = frappe.form_dict["name"]
			context.email_groups = get_email_groups(user_email)
			context.current_group = get_current_groups(tittle)
		else:
			print("============inside====================")
			context.valid = "not found"

def get_email_groups(user_email):
	return frappe.get_all("Email Group Member", fields = ["email_group"], filters = {"email": user_email})

def get_current_groups(name):
	return frappe.db.get_all("Newsletter Email Group", ["email_group"],{"parent":name, "parenttype":"Newsletter"})