# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class LinkFieldFilter(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		condition: DF.Literal
		field: DF.Literal
		link_field: DF.Literal
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		value: DF.Data | None
	# end: auto-generated types
	pass
