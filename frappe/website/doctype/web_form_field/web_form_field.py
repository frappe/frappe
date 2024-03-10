# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class WebFormField(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		allow_read_on_all_link_options: DF.Check
		default: DF.Data | None
		depends_on: DF.Code | None
		description: DF.Text | None
		fieldname: DF.Literal[None]
		fieldtype: DF.Literal[
			"Attach",
			"Attach Image",
			"Check",
			"Currency",
			"Color",
			"Data",
			"Date",
			"Datetime",
			"Duration",
			"Float",
			"HTML",
			"Int",
			"Link",
			"Password",
			"Phone",
			"Rating",
			"Select",
			"Signature",
			"Small Text",
			"Text",
			"Text Editor",
			"Table",
			"Time",
			"Section Break",
			"Column Break",
			"Page Break",
		]
		hidden: DF.Check
		label: DF.Data | None
		mandatory_depends_on: DF.Code | None
		max_length: DF.Int
		max_value: DF.Int
		options: DF.Text | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		precision: DF.Literal["", "0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
		read_only: DF.Check
		read_only_depends_on: DF.Code | None
		reqd: DF.Check
		show_in_filter: DF.Check
	# end: auto-generated types

	pass
