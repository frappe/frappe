# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class RolePermissionforPageandReport(Document):
	def get_custom_roles(self):
		args = self.get_args()
		self.set('roles', [])

		name = frappe.db.get_value('Custom Role', args, "name")
		if name:
			doc = frappe.get_doc('Custom Role', name)
			roles = doc.roles
		else:
			roles = self.get_standard_roles()

		self.set('roles', roles)
		
	def get_standard_roles(self):
		doctype = self.set_role_for
		docname = self.page if self.set_role_for == 'Page' else self.report
		doc = frappe.get_doc(doctype, docname)
		return doc.roles

	def reset_roles(self):
		roles = self.get_standard_roles()
		self.set('roles', roles)
		self.set_custom_roles()

	def set_custom_roles(self):
		args = self.get_args()
		name = frappe.db.get_value('Custom Role', args, "name")

		args.update({
			'doctype': 'Custom Role',
			'roles': self.get_roles()
		})

		if self.report:
			args.update({'ref_doctype': frappe.db.get_value('Report', self.report, 'ref_doctype')})

		if name:
			custom_role = frappe.get_doc("Custom Role", name)
			custom_role.set('roles', self.get_roles())
			custom_role.save()
		else:
			frappe.get_doc(args).insert()

	def get_args(self, row=None):
		name = self.page if self.set_role_for == 'Page' else self.report
		check_for_field = self.set_role_for.replace(" ","_").lower()

		return {
			check_for_field: name
		}
		
	def get_roles(self):
		roles = []
		for data in self.roles:
			roles.append({
				'role': data.role,
				'parenttype': 'Custom Role'
			})
		return roles

	def update_status(self):
		return frappe.render_template
