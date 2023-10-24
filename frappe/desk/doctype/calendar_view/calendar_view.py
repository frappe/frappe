# Copyright (c) 2017, Frappe Technologies and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class CalendarView(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		all_day: DF.Check
		end_date_field: DF.Literal
		reference_doctype: DF.Link
		start_date_field: DF.Literal
		subject_field: DF.Literal
	# end: auto-generated types
	pass
