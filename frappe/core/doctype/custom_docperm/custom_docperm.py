# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class CustomDocPerm(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		amend: DF.Check
		cancel: DF.Check
		create: DF.Check
		delete: DF.Check
		email: DF.Check
		export: DF.Check
		if_owner: DF.Check
		parent: DF.Data | None
		permlevel: DF.Int
		print: DF.Check
		read: DF.Check
		report: DF.Check
		role: DF.Link
		select: DF.Check
		share: DF.Check
		submit: DF.Check
		write: DF.Check
	# end: auto-generated types

	def on_update(self):
		frappe.clear_cache(doctype=self.parent)

	def get_permission_log_options(self, event=None):
		return {"for_doctype": "DocType", "for_document": self.parent}


def update_custom_docperm(docperm, values):
	custom_docperm = frappe.get_doc("Custom DocPerm", docperm)
	custom_docperm.update(values)
	custom_docperm.save(ignore_permissions=True)
