# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class WidgetTypeField(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		default: DF.SmallText | None
		description: DF.SmallText | None
		fieldname: DF.Data
		fieldtype: DF.Literal[
			"Data",
			"Select",
			"Link",
			"Dynamic Link",
			"Check",
			"Int",
			"Float",
			"Currency",
			"Small Text",
			"Code",
			"JSON",
			"Table",
			"Icon",
			"Color",
		]
		in_standard_filter: DF.Check
		label: DF.Data | None
		options: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		reqd: DF.Check
	# end: auto-generated types

	_DOCTYPE_NAME = "Widget Type Field"
