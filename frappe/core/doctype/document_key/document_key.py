# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class DocumentKey(Document):
	def before_insert(self):
		self.key = frappe.generate_hash(length=32)
		if not self.expires_on:
			meta = frappe.get_meta("DocType", self.reference_doctype)
			self.expires_on = frappe.utils.add_days(None, days=meta.get("document_key_expiry") or 90)

	def is_expired(self):
		return self.expires_on < frappe.utils.getdate()
