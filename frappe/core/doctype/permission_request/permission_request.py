# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.desk.form import assign_to
from frappe.model.document import Document


class PermissionRequest(Document):
	def validate(self):
		self.validate_authorizer()

	def after_insert(self):
		self.assign_request()

	def validate_authorizer(self):
		# Explicit validation, since the set_query filter for this DocType
		# doesn't filter current user
		if self.user == self.authorizer:
			frappe.throw(_("Authorizer cannot be the same as the requesting User"))

	def assign_request(self):
		assign_to.add({
			'assign_to': self.authorizer,
			'doctype': self.doctype,
			'name': self.name,
			'description': self.reason or self.name,
		})
