# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class UserType(Document):
	def on_update(self):
		self.validate_document_limits()
		self.update_document_type()

	def update_document_type(self):
		if self.is_standard: return

		frappe.cache().hdel('user_doctype', self.name)
		doctypes = [d.document_type for d in self.user_doctypes]
		frappe.cache().hset('user_doctype', self.name, doctypes)

	def on_trash(self):
		if self.is_standard:
			frappe.throw(_('Standard user type {0} can not be deleted.')
				.format(frappe.bold(self.name)))

	def validate_document_limits(self):
		if self.is_standard: return

		limit = frappe.conf.get('user_type_doctype_limit') or 25

		doctypes = frappe.get_all('User Type', filters = {'is_standard': 0})
		if not doctypes: return

		user_doctypes = frappe.get_all('User Document Type',
			filters = {'parent': ('in', [d.name for d in doctypes])})

		if user_doctypes and len(user_doctypes) > limit:
			frappe.throw(_('The total number of user document types limit has been crossed.'),
				title=_('Please contact Administrator / Tech support'))

def get_user_document_types(user_type):
	doctypes = frappe.cache().hget('user_doctype', user_type)

	if not doctypes:
		data = frappe.get_all('User Document Type', fields = ['document_type'],
			filters = {'parent': user_type})

		doctypes = [d.document_type for d in data]

	return doctypes