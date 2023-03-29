# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class CustomDocPerm(Document):
	def on_update(self):
		frappe.clear_cache(doctype=self.parent)

	def for_perm_log(self):
		return {"for_doctype": "DocType", "for_document": self.parent}


def update_custom_docperm(docperm, values):
	custom_docperm = frappe.get_doc("Custom DocPerm", docperm)
	custom_docperm.update(values)
	custom_docperm.save(ignore_permissions=True)
