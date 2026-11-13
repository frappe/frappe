# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.printing.doctype.print_format.print_designer_converter import (
	create_editor_format,
	print_format_references,
)


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
		filters={"print_designer": 1},
		or_filters=or_filters,
		fields=["name", "doc_type", "disabled", "standard"],
		order_by="doc_type asc, name asc",
	)
	copies = editor_copies(rows)
	for row in rows:
		row.editor_format = copies.get(row.name)
		if not row.editor_format:
			row.state = "Not converted"
		elif not row.disabled:
			row.state = "Converted"
		else:
			row.state = "Switched over"
			row.can_delete = row.standard == "No" and not print_format_references(row.name)
	return rows


def editor_copies(rows: list[dict]) -> dict[str, str]:
	names = [row.name for row in rows]
	copies = {}
	for copy in frappe.get_all(
		"Print Format",
		filters={"converted_from": ["in", names]},
		fields=["name", "converted_from"],
		order_by="creation desc",
	):
		copies.setdefault(copy.converted_from, copy.name)

	named = {_("{0} (Editor)").format(row.name): row for row in rows if row.name not in copies}
	if named:
		for copy in frappe.get_all(
			"Print Format",
			filters={
				"name": ["in", list(named)],
				"print_format_builder_beta": 1,
				"converted_from": ["is", "not set"],
			},
			fields=["name", "doc_type"],
		):
			source = named[copy.name]
			if copy.doc_type == source.doc_type:
				copies[source.name] = copy.name
	return copies


@frappe.whitelist(methods=["POST"])
def convert_all() -> dict:
	frappe.only_for("System Manager")
	converted, failed = [], []
	for row in get_print_designer_formats():
		if row.state != "Not converted":
			continue
		frappe.db.savepoint("convert_print_designer_format")
		try:
			converted.append(create_editor_format(row.name)["name"])
		except Exception:
			frappe.db.rollback(save_point="convert_print_designer_format")
			frappe.log_error(f"Could not convert Print Designer format {row.name}")
			failed.append(row.name)
	return {"converted": converted, "failed": failed}
