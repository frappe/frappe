# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.modules.export_file import export_to_files
from frappe.query_builder.utils import DocType


class CustomHTMLBlock(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.has_role.has_role import HasRole
		from frappe.types import DF

		html: DF.Code | None
		is_standard: DF.Check
		module: DF.Link | None
		private: DF.Check
		roles: DF.Table[HasRole]
		script: DF.Code | None
		style: DF.Code | None
	# end: auto-generated types

	def on_update(self):
		if frappe.conf.developer_mode and self.is_standard:
			export_to_files(record_list=[["Custom HTML Block", self.name]], record_module=self.module)


@frappe.whitelist()
def get_custom_blocks_for_user(doctype, txt, searchfield, start, page_len, filters):
	# return logged in users private blocks and all public blocks
	customHTMLBlock = DocType("Custom HTML Block")

	condition_query = frappe.qb.from_(customHTMLBlock)

	return (
		condition_query.select(customHTMLBlock.name).where(
			(customHTMLBlock.private == 0)
			| ((customHTMLBlock.owner == frappe.session.user) & (customHTMLBlock.private == 1))
		)
	).run()
