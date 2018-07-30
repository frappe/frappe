# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ActionSetValue(Document):
	def execute(self, doc):
		if self.dynamic_value:
			value = frappe.safe_eval(self.formula, context=dict(doc = doc))
		else:
			value = self.value

		if doc.flags.automation_before_save:
			doc.set(self.fieldname, value)
		else:
			doc.db_set(self.fieldname, value)
