# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.printing.doctype.print_format.print_designer_converter import (
	convert,
	converted_values,
	editor_copy,
	is_print_designer_format,
	print_format_usage,
)
from frappe.printing.doctype.print_format.print_format import printable_sample


@frappe.whitelist()
def get_print_designer_formats() -> list[dict]:
	frappe.only_for("System Manager")
	meta = frappe.get_meta("Print Format")
	or_filters = [
		[field, "is", "set"]
		for field in ("print_designer_body", "print_designer_print_format")
		if meta.has_field(field)
	]
	if not meta.has_field("print_designer") or not or_filters:
		return []

	rows = frappe.get_all(
		"Print Format",
		or_filters=or_filters,
		fields=["name", "doc_type", "disabled", "standard", "print_designer", "print_format_builder_beta"],
		order_by="doc_type asc, name asc",
	)
	rows = [
		row
		for row in rows
		if (row.print_designer or row.print_format_builder_beta) and frappe.db.exists("DocType", row.doc_type)
	]
	copies = set()
	for row in rows:
		row.editor_format = row.name
		row.converted = not row.print_designer
		if row.standard == "Yes":
			copy = editor_copy(row)
			row.converted = bool(copy)
			row.editor_format = copy.name if copy else None
			if copy:
				copies.add(copy.name)
				row.usage = print_format_usage(row.name)
	rows = [row for row in rows if row.name not in copies]

	samples = {}
	for row in rows:
		if row.doc_type not in samples:
			samples[row.doc_type] = None
			if frappe.has_permission(row.doc_type):
				samples[row.doc_type] = printable_sample(row.doc_type)
		row.sample = samples[row.doc_type]
	return rows


@frappe.whitelist(methods=["POST"])
def convert_all() -> dict:
	frappe.only_for("System Manager")
	converted, failed = [], []
	for row in get_print_designer_formats():
		if row.converted or row.standard == "Yes":
			continue
		frappe.db.savepoint("convert_print_designer_format")
		try:
			convert(row.name)
			converted.append(row.name)
		except Exception:
			frappe.db.rollback(save_point="convert_print_designer_format")
			frappe.log_error(f"Could not convert Print Designer format {row.name}")
			failed.append(row.name)
	return {"converted": converted, "failed": failed}


@frappe.whitelist()
def preview_conversion(print_format: str, name: str | None = None) -> None:
	from frappe.utils.print_format_generator import download_builder_preview_pdf

	frappe.only_for("System Manager")
	doc = frappe.get_doc("Print Format", print_format)
	if not is_print_designer_format(doc):
		frappe.throw(_("{0} is not a Print Designer format.").format(frappe.bold(print_format)))
	converted = doc.as_dict()
	converted.update(converted_values(doc)[0], name=None)
	download_builder_preview_pdf(converted, doc.doc_type, name)
