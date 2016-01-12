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
