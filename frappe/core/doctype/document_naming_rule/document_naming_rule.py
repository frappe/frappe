# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils.data import evaluate_filters

class DocumentNamingRule(Document):
	def apply(self, doc):
		if self.conditions:
			if not evaluate_filters(doc, [(d.field, d.condition, d.value) for d in self.conditions]):
				return

		if self.naming_by == 'Field Value':
			doc.name = doc.get(self.naming_field)

		elif self.naming_by == 'Numbered':
			counter = frappe.db.get_value(self.doctype, self.name, 'counter', for_update=True) or 0
			doc.name = self.prefix + ('%0'+str(self.prefix_digits)+'d') % (counter + 1)
			frappe.db.set_value(self.doctype, self.name, 'counter', counter + 1)

		elif self.naming_by == 'Default':
			doc.name = frappe.generate_hash(doc.doctype, 10)
