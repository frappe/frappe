# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class VCSDoctype(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.vcs_doctype_item.vcs_doctype_item import VCSDoctypeItem
		from frappe.types import DF

		vcs_doctypes: DF.Table[VCSDoctypeItem]
	# end: auto-generated types
	pass
