# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.model.document import Document

class Role(Document):
	def before_rename(self, old, new, merge=False):
		if old in ("Guest", "Administrator", "System Manager", "All"):
			frappe.throw(frappe._("Standard roles cannot be renamed"))

	def after_insert(self):
		# Add role to Administrator
		if frappe.flags.in_install != "frappe":
			user = frappe.get_doc("User", "Administrator")
			user.flags.ignore_permissions = True
			user.add_roles(self.name)
	
	def validate(self):
		if self.disabled:
			if self.name in ("Guest", "Administrator", "System Manager", "All"):
				frappe.throw(frappe._("Standard roles cannot be disabled"))
			else:
				frappe.db.sql("delete from `tabHas Role` where role = %s", self.name)
				frappe.clear_cache()

# Get email addresses of all users that have been assigned this role
def get_emails_from_role(role):
	emails = []

	users = frappe.get_list("Has Role", filters={"role": role, "parenttype": "User"},
		fields=["parent"])

	for user in users:
		user_email = frappe.db.get_value("User", user.parent, "email")
		emails.append(user_email)
	
	return emails