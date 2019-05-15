# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document


class PermissionRequest(Document):
	def validate(self):
		self.validate_duplicate_request()

	def validate_duplicate_request(self):
		if self.status == "Requested":
			filters = {
				"doc_type": self.doc_type,
				"user": self.user,
				"name": ["!=", self.name],
				"status": "Requested"
			}

			if frappe.db.exists("Permission Request", filters):
				frappe.throw(_("A Permission Request already exists for this DocType and User"), frappe.DuplicateEntryError)
