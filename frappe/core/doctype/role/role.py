# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.website.path_resolver import validate_path
from frappe.website.router import clear_routing_cache

STANDARD_ROLES = ("Administrator", "System Manager", "Script Manager", "All", "Guest")


class Role(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		desk_access: DF.Check
		disabled: DF.Check
		home_page: DF.Data | None
		is_custom: DF.Check
		restrict_to_domain: DF.Link | None
		role_name: DF.Data
		two_factor_auth: DF.Check
	# end: auto-generated types

	def before_rename(self, old, new, merge: bool = False) -> None:
		if old in STANDARD_ROLES:
			frappe.throw(frappe._("Standard roles cannot be renamed"))

	def after_insert(self) -> None:
		frappe.cache.hdel("roles", "Administrator")

	def validate(self) -> None:
		if self.disabled:
			self.disable_role()
		else:
			self.set_desk_properties()
		self.validate_homepage()

	def disable_role(self) -> None:
		if self.name in STANDARD_ROLES:
			frappe.throw(frappe._("Standard roles cannot be disabled"))
		else:
			self.remove_roles()

	def validate_homepage(self) -> None:
		if frappe.request and self.home_page:
			validate_path(self.home_page)

		if self.has_value_changed("home_page"):
			clear_routing_cache()

	def set_desk_properties(self) -> None:
		# set if desk_access is not allowed, unset all desk properties
		if self.name == "Guest":
			self.desk_access = 0

	def remove_roles(self) -> None:
		frappe.db.delete("Has Role", {"role": self.name})
		frappe.clear_cache()

	def on_update(self) -> None:
		"""update system user desk access if this has changed in this update"""
		if frappe.flags.in_install:
			return
		if self.has_value_changed("desk_access"):
			self.update_user_type_on_change()

	def update_user_type_on_change(self) -> None:
		"""When desk access changes, all the users that have this role need to be re-evaluated"""

		users_with_role = get_users(self.name)

		# perf: Do not re-evaluate users who already have same desk access that this role permits.
		role_user_type = "System User" if self.desk_access else "Website User"
		users_with_same_user_type = frappe.get_all("User", {"user_type": role_user_type}, pluck="name")

		for user_name in set(users_with_role) - set(users_with_same_user_type):
			user = frappe.get_doc("User", user_name)
			user_type = user.user_type
			user.set_system_user()
			if user_type != user.user_type:
				user.save()


def get_info_based_on_role(role, field: str = "email", ignore_permissions: bool = False):
	"""Get information of all users that have been assigned this role"""
	users = frappe.get_list(
		"Has Role",
		filters={"role": role, "parenttype": "User"},
		parent_doctype="User",
		fields=["parent as user_name"],
		ignore_permissions=ignore_permissions,
	)

	return get_user_info(users, field)


def get_user_info(users, field: str = "email"):
	"""Fetch details about users for the specified field"""
	info_list = []
	for user in users:
		user_info, enabled = frappe.db.get_value("User", user.get("user_name"), [field, "enabled"])
		if enabled and user_info not in ["admin@example.com", "guest@example.com"]:
			info_list.append(user_info)
	return info_list


def get_users(role):
	return [
		d.parent
		for d in frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, fields=["parent"])
	]


# searches for active employees
@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def role_query(doctype, txt, searchfield, start, page_len, filters):
	report_filters = [["Role", "name", "like", f"%{txt}%"], ["Role", "is_custom", "=", 0]]
	if filters and isinstance(filters, list):
		report_filters.extend(filters)

	return frappe.get_all(
		"Role", limit_start=start, limit_page_length=page_len, filters=report_filters, as_list=1
	)
