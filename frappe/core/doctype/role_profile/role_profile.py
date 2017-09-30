# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class RoleProfile(Document):
	def autoname(self):
		"""set name as Role Name"""
		self.name = self.role_name

	def on_update(self):
		roles = [x.role for x in self.roles]
		users = frappe.get_all('User', filters={'role_name': self.role_name})

		for d in users:
			user = frappe.get_doc('User', d)
			user_roles = [role for role in user.roles]
			for role in roles:
				if role not in user_roles:
					user.append('roles', {
							'role': role
						})
			user.save(ignore_permissions=True)
