# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class RoleProfile(Document):
	def autoname(self):
		"""set name as Role Profile name"""
		self.name = self.role_profile

	def on_update(self):
		"""Changes in role_profile reflected across all its user"""
		users = frappe.get_all("User", filters={"role_profile_name": self.name})
		roles = [role.role for role in self.roles]
		for d in users:
			user = frappe.get_doc("User", d)
			user.set("roles", [])
			user.add_roles(*roles)
