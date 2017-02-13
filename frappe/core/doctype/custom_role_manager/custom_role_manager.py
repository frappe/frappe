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
		
		self.set('roles', [])
		for data in frappe.get_all('Custom Role', 
			filters=args, fields=['role', 'page', 'report']):
			self.append('roles', {
				'report': data.report,
				'page': data.page,
				'role': data.role
			})

	def set_custom_roles(self):
		for d in self.roles:
			args = self.get_args(d)
			name = frappe.db.get_value('Custom Role', args, "role")
			if not name:
				args.update({'doctype': "Custom Role"})
				self.make_custom_role(args)
				frappe.msgprint(_("Successfully Updated"))

	def get_args(self, row=None):
		args = {}
		name = self.page if self.set_role_for == 'Page' else self.report
		check_for = self.set_role_for.replace(" ","_").lower()
		
		args = {check_for: name}
		if row:
			args.update({'role': row.role})

		return args

	def make_custom_role(self, args):
		frappe.get_doc(args).insert()
