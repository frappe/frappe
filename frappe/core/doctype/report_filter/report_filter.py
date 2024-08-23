# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

# import frappe
from frappe.model.document import Document


class ReportFilter(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		default: DF.SmallText | None
		fieldname: DF.Data
		fieldtype: DF.Literal[
			"Check",
			"Currency",
			"Data",
			"Date",
			"Datetime",
			"Dynamic Link",
			"Float",
			"Fold",
			"Int",
			"Link",
			"Select",
			"Time",
		]
		label: DF.Data
		mandatory: DF.Check
		options: DF.SmallText | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		wildcard_filter: DF.Check
	# end: auto-generated types

	pass
