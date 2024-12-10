# Copyright (c) 2017, Frappe Technologies and contributors
# License: MIT. See LICENSE

from collections import defaultdict

import frappe
from frappe.model.document import Document


class RoleProfile(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.has_role.has_role import HasRole
		from frappe.types import DF

		role_profile: DF.Data
		roles: DF.Table[HasRole]
<<<<<<< HEAD

	# end: auto-generated types
=======
	# end: auto-generated types

>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	def autoname(self):
		"""set name as Role Profile name"""
		self.name = self.role_profile

	def on_update(self):
		self.queue_action(
			"update_all_users",
			now=frappe.flags.in_test or frappe.flags.in_install,
			enqueue_after_commit=True,
<<<<<<< HEAD
=======
			queue="long",
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		)

	def update_all_users(self):
		"""Changes in role_profile reflected across all its user"""
<<<<<<< HEAD
		has_role = frappe.qb.DocType("Has Role")
		user = frappe.qb.DocType("User")

		all_current_roles = (
			frappe.qb.from_(user)
			.join(has_role)
			.on(user.name == has_role.parent)
			.where(user.role_profile_name == self.name)
			.select(user.name, has_role.role)
		).run()

		user_roles = defaultdict(set)
		for user, role in all_current_roles:
			user_roles[user].add(role)

		role_profile_roles = {role.role for role in self.roles}
		for user, roles in user_roles.items():
			if roles != role_profile_roles:
				user = frappe.get_doc("User", user)
				user.roles = []
				user.add_roles(*role_profile_roles)
=======
		users = frappe.get_all("User Role Profile", filters={"role_profile": self.name}, pluck="parent")
		for user in users:
			user = frappe.get_doc("User", user)
			user.save()  # resaving syncs roles

	def get_permission_log_options(self, event=None):
		return {"fields": ["roles"]}
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
