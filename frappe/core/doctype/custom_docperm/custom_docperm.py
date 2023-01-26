# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class CustomDocPerm(Document):
	def on_update(self):
		frappe.clear_cache(doctype=self.parent)
