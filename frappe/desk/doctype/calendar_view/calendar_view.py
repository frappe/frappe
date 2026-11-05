# Copyright (c) 2017, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model import no_value_fields
from frappe.model.document import Document


class CalendarView(Document):
	_DOCTYPE_NAME = "Calendar View"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		all_day: DF.Check
		end_date_field: DF.Literal[None]
		reference_doctype: DF.Link
		start_date_field: DF.Literal[None]
		subject_field: DF.Literal[None]
	# end: auto-generated types

	def validate(self):
		meta = frappe.get_meta(self.reference_doctype)
		for fieldname in ("start_date_field", "end_date_field"):
			value = self.get(fieldname)
			if value and getattr(meta.get_field(value), "fieldtype", None) not in ("Date", "Datetime"):
				frappe.throw(_("{0} must be a Date or Datetime field").format(self.meta.get_label(fieldname)))

		if self.subject_field and getattr(meta.get_field(self.subject_field), "fieldtype", None) in (
			None,
			*no_value_fields,
		):
			frappe.throw(
				_("{0} must be a field that holds a value").format(self.meta.get_label("subject_field"))
			)
