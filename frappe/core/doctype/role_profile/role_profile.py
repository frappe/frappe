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
	# end: auto-generated types

	def autoname(self):
		"""set name as Role Profile name"""
		self.name = self.role_profile

	def on_update(self):
		self.queue_action(
			"update_all_users",
			now=frappe.flags.in_test or frappe.flags.in_install,
			enqueue_after_commit=True,
		)

	def update_all_users(self):
		"""Changes in role_profile reflected across all its user"""
		users = frappe.get_list("User Role Profile", filters={"role_profile": self.name}, pluck="parent")
		for user in users:
			role_profile_roles = []
			user = frappe.get_doc("User", user)
			for role_profile in user.role_profiles:
				if self.name == role_profile.role_profile:
					continue
				profile = frappe.get_doc("Role Profile", role_profile.role_profile)
				role_profile_roles.extend([role.role for role in profile.roles])
			role_profile_roles.extend([role.role for role in self.roles])
			role_profile_roles = list(set(role_profile_roles))
			user.roles = []
			user.add_roles(*role_profile_roles)
