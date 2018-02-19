# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class AddFetch(Document):
	def validate(self):
		exist = frappe.db.get_value('Add Fetch',
			{"for_doctype": self.for_doctype,
			"for_fieldname": self.for_fieldname,
			"from_doctype": self.from_doctype,
			"from_fieldname": self.from_fieldname})
		if exist:
			raise frappe.DuplicateEntryError
