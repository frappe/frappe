# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class CustomDocPerm(Document):
	def before_save(self):
		if self.is_new():
			pass

	def on_update(self):
		frappe.clear_cache(doctype=self.parent)

	def on_trash(self):
		pass


def update_custom_docperm(docperm, values):
	custom_docperm = frappe.get_doc("Custom DocPerm", docperm)
	custom_docperm.update(values)
	custom_docperm.save(ignore_permissions=True)
