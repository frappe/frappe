# Copyright (c) 2017, Frappe Technologies and contributors
# License: MIT. See LICENSE

from collections import defaultdict

import frappe
from frappe.model.document import Document


class RoleProfile(Document):
	def autoname(self):
		"""set name as Role Profile name"""
		self.name = self.role_profile

	def on_update(self):
		"""Changes in role_profile reflected across all its user"""
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
