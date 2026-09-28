import frappe
from frappe.query_builder import DocType


def execute():
	"""Backfill `print_format_for` on rows that predate the field.

	Formats created before it existed carry NULL, and the print page filters the
	Print Format picker on `print_format_for = "DocType"`, so those formats went
	missing from the dropdown.
	"""
	print_format = DocType("Print Format")
	(
		frappe.qb.update(print_format)
		.set(print_format.print_format_for, "DocType")
		.where(print_format.print_format_for.isnull() | (print_format.print_format_for == ""))
	).run()
