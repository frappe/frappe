# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DocumentAttachmentRules(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.document_attachment_template.document_attachment_template import DocumentAttachmentTemplate
		from frappe.types import DF

		attachments: DF.Table[DocumentAttachmentTemplate]
		disabled: DF.Check
		document_type: DF.Link
	# end: auto-generated types

	def on_update(self):
		self.clear_meta_cache()

	def on_trash(self):
		self.clear_meta_cache()

	def clear_meta_cache(self):
		"""Clear meta cache for the target doctype so attachments tab appears/disappears."""
		if self.document_type:
			frappe.clear_cache(doctype=self.document_type)

