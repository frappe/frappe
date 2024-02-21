# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class PrintFormatFieldTemplate(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		document_type: DF.Link
		field: DF.Data | None
		module: DF.Link | None
		standard: DF.Check
		template: DF.Code | None
		template_file: DF.Data | None
	# end: auto-generated types

	def validate(self):
		if self.standard and not frappe.conf.developer_mode and not frappe.flags.in_patch:
			frappe.throw(_("Enable developer mode to create a standard Print Template"))

	def before_insert(self):
		self.validate_duplicate()

	def on_update(self):
		self.validate_duplicate()
		self.export_doc()

	def validate_duplicate(self):
		if not self.standard:
			return
		if not self.field:
			return

		filters = {"document_type": self.document_type, "field": self.field}
		if not self.is_new():
			filters.update({"name": ("!=", self.name)})
		result = frappe.get_all("Print Format Field Template", filters=filters, limit=1)
		if result:
			frappe.throw(
				_("A template already exists for field {0} of {1}").format(
					frappe.bold(self.field), frappe.bold(self.document_type)
				),
				frappe.DuplicateEntryError,
				title=_("Duplicate Entry"),
			)

	def export_doc(self):
		from frappe.modules.utils import export_module_json

		export_module_json(self, self.standard, self.module)
