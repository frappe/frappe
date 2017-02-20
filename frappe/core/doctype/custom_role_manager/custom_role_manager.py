# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class CustomRoleManager(Document):
	def get_custom_roles(self):
		args = self.get_args()
		name = frappe.db.get_value('Custom Role', args, "name")
		if not name:
			self.set('has_roles', [])
			return

		doc = frappe.get_doc('Custom Role', name)
		self.set('has_roles', doc.roles)

	def set_custom_roles(self):
		args = self.get_args()
		name = frappe.db.get_value('Custom Role', args, "name")

		args.update({
			'doctype': 'Custom Role',
			'has_roles': self.has_roles
		})

		if name:
			doc = frappe.get_doc("Custom Role", name)
			doc.set('has_roles', self.has_roles)
			doc.save()
		else:
			frappe.get_doc(args).insert()

	def get_args(self, row=None):
		name = self.page if self.set_role_for == 'Page' else self.report
		check_for_field = self.set_role_for.replace(" ","_").lower()

		return {
			check_for_field: name
		}
		
	def update_status(self):
		return frappe.render_template