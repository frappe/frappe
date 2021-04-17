# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

from frappe.model.document import Document

desk_properties = ("search_bar", "notifications", "chat", "list_sidebar",
	"bulk_actions", "view_switcher", "form_sidebar", "timeline", "dashboard")

class Role(Document):
	def before_rename(self, old, new, merge=False):
		if old in ("Guest", "Administrator", "System Manager", "All"):
			frappe.throw(frappe._("Standard roles cannot be renamed"))

	def after_insert(self):
		frappe.cache().hdel('roles', 'Administrator')

	def validate(self):
		if self.disabled:
			self.disable_role()
		else:
			self.set_desk_properties()

	def disable_role(self):
		if self.name in ("Guest", "Administrator", "System Manager", "All"):
			frappe.throw(frappe._("Standard roles cannot be disabled"))
		else:
			self.remove_roles()

	def set_desk_properties(self):
		# set if desk_access is not allowed, unset all desk properties
		if self.name == 'Guest':
			self.desk_access = 0

		if not self.desk_access:
			for key in desk_properties:
				self.set(key, 0)

	def remove_roles(self):
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

def get_info_based_on_role(role, field='email'):
	''' Get information of all users that have been assigned this role '''
	users = frappe.get_list("Has Role", filters={"role": role, "parenttype": "User"},
		fields=["parent as user_name"])

	return get_user_info(users, field)

def get_user_info(users, field='email'):
	''' Fetch details about users for the specified field '''
	info_list = []
	for user in users:
		user_info, enabled = frappe.db.get_value("User", user.get("user_name"), [field, "enabled"])
		if enabled and user_info not in ["admin@example.com", "guest@example.com"]:
			info_list.append(user_info)
	return info_list

def get_users(role):
	return [d.parent for d in frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"},
		fields=["parent"])]


# searches for active employees
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def role_query(doctype, txt, searchfield, start, page_len, filters):
	report_filters = [['Role', 'name', 'like', '%{}%'.format(txt)], ['Role', 'is_custom', '=', 0]]
	if filters and isinstance(filters, list):
		report_filters.extend(filters)

	return frappe.get_all('Role', limit_start=start, limit_page_length=page_len,
		filters=report_filters, as_list=1)