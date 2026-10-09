# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.model.document import Document


class PrintFormatSnippet(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		content: DF.Code
		document_type: DF.Link | None
		module: DF.Link | None
		snippet_type: DF.Literal["Section", "Field"]
		standard: DF.Check
	# end: auto-generated types

	def validate(self):
		self.validate_content()

		if self.standard:
			if not frappe.conf.developer_mode and not frappe.flags.in_patch:
				frappe.throw(_("Enable developer mode to create a standard Print Format Snippet"))
			if not self.module:
				frappe.throw(_("Module is required for a standard Print Format Snippet"))

	def validate_content(self):
		# validate() runs before the mandatory check, so content can still be None here
		if not self.content:
			return

		try:
			content = json.loads(self.content)
		except (TypeError, ValueError):
			frappe.throw(_("Content must be valid JSON"), title=_("Invalid Snippet"))

		if not isinstance(content, dict):
			frappe.throw(_("Content must be a JSON object"), title=_("Invalid Snippet"))

	def on_update(self):
		self.export_doc()

	def export_doc(self):
		from frappe.modules.utils import export_module_json

		export_module_json(self, self.standard, self.module)
