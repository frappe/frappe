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
		frappe.cache().hdel('roles', 'Administrator')

	def validate(self):
		if self.disabled:
			if self.name in ("Guest", "Administrator", "System Manager", "All"):
				frappe.throw(frappe._("Standard roles cannot be disabled"))
			else:
				frappe.db.sql("delete from `tabHas Role` where role = %s", self.name)
				frappe.clear_cache()

	def on_update(self):
		'''update system user desk access if this has changed in this update'''
		if frappe.flags.in_install: return
		if self.has_value_changed('desk_access'):
			for user_name in get_users(self.name):
				user = frappe.get_doc('User', user_name)
				user_type = user.user_type
				user.set_system_user()
				if user_type != user.user_type:
					user.save()

# Get email addresses of all users that have been assigned this role
def get_emails_from_role(role):
	emails = []

	for user in get_users(role):
		user_email, enabled = frappe.db.get_value("User", user, ["email", "enabled"])
		if enabled and user_email not in ["admin@example.com", "guest@example.com"]:
			emails.append(user_email)

	return emails

def get_users(role):
	return [d.parent for d in frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"},
		fields=["parent"])]
