# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.utils.data import evaluate_filters
from frappe import _

class DocumentNamingRule(Document):
	def validate(self):
		self.validate_fields_in_conditions()

	def validate_fields_in_conditions(self):
		if self.has_value_changed("document_type"):
			docfields = [x.fieldname for x in frappe.get_meta(self.document_type).fields]
			for condition in self.conditions:
				if condition.field not in docfields:
					frappe.throw(_("{0} is not a field of doctype {1}").format(frappe.bold(condition.field), frappe.bold(self.document_type)))

	def apply(self, doc):
		'''
		Apply naming rules for the given document. Will set `name` if the rule is matched.
		'''
		if self.conditions:
			if not evaluate_filters(doc, [(self.document_type, d.field, d.condition, d.value) for d in self.conditions]):
				return

		counter = frappe.db.get_value(self.doctype, self.name, 'counter', for_update=True) or 0
		doc.name = self.prefix + ('%0'+str(self.prefix_digits)+'d') % (counter + 1)
		frappe.db.set_value(self.doctype, self.name, 'counter', counter + 1)
