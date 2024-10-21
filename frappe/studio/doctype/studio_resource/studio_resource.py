# Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class StudioResource(Document):
	def before_insert(self):
		if isinstance(self.fields, list):
			self.fields = frappe.as_json(self.fields, indent=None)

		if isinstance(self.filters, list):
			self.filters = frappe.as_json(self.filters, indent=None)

		if isinstance(self.whitelisted_methods, list):
			self.whitelisted_methods = frappe.as_json(self.whitelisted_methods, indent=None)
