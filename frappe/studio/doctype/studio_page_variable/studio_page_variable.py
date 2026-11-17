# Copyright (c) 2025, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class StudioPageVariable(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		initial_value: DF.Code | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		variable_name: DF.Data
		variable_type: DF.Literal["String", "Number", "Boolean", "Object"]
	# end: auto-generated types

	pass
