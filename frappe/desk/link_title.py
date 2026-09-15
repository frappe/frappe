# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""Resolve `show_title_field_in_link` titles for sets of link values."""

import frappe
from frappe.model import get_permitted_fields
from frappe.utils import create_batch

TITLE_BATCH_SIZE = 500


def get_link_title_field(doctype: str) -> str | None:
	"""Title field configured for `doctype`, or None when the user may not read it."""
	meta = frappe.get_meta(doctype)
	if not (meta.show_title_field_in_link and meta.title_field):
		return None

	title_field = meta.title_field.strip()
	if title_field == "name" or not frappe.has_permission(doctype):
		return None
	if title_field not in get_permitted_fields(doctype, ignore_virtual=True):
		return None

	return title_field


def get_link_titles(doctype: str, title_field: str, names: set[str]) -> dict[str, str]:
	"""Titles of the readable documents among `names`, keyed by document name."""
	titles = {}
	for names_batch in create_batch(list(names), TITLE_BATCH_SIZE):
		rows = frappe.get_list(
			doctype,
			filters={"name": ("in", names_batch)},
			fields=["name", title_field],
			limit=len(names_batch),
		)
		titles.update({row.name: row.get(title_field) for row in rows})
	return titles


def send_link_titles(link_titles: dict[str, str]):
	"""Append link titles dict in `frappe.local.response`."""
	if "_link_titles" not in frappe.local.response:
		frappe.local.response["_link_titles"] = {}

	frappe.local.response["_link_titles"].update(link_titles)


def get_report_link_titles(columns, rows) -> dict[str, str]:
	"""Titles for the Link values in `rows`, keyed `doctype::name` for the client cache."""
	titles = {}
	names_by_doctype = get_link_names_by_doctype(columns or [], rows or [])
	for doctype, names in names_by_doctype.items():
		title_field = get_link_title_field(doctype)
		if not title_field:
			continue
		for name, title in get_link_titles(doctype, title_field, names).items():
			titles[f"{doctype}::{name}"] = title
	return titles


def set_link_titles_in_rows(columns, rows) -> list:
	"""Copy of `rows` with Link values replaced by their configured titles.

	For exported files, which are read rather than re-imported. A `name` column is left
	alone, so the export keeps an identifier usable for lookups.
	"""
	link_columns = [
		(index, fieldname, doctype)
		for index, fieldname, doctype in get_link_columns(columns or [])
		if fieldname != "name"
	]

	titles_by_doctype = {}
	for doctype, names in get_names_by_doctype(link_columns, rows or []).items():
		if title_field := get_link_title_field(doctype):
			titles_by_doctype[doctype] = get_link_titles(doctype, title_field, names)

	titled_rows = []
	for row in rows or []:
		row = dict(row) if isinstance(row, dict) else list(row)
		for index, fieldname, doctype in link_columns:
			titles = titles_by_doctype.get(doctype)
			name = get_row_value(row, fieldname, index)
			if titles and name:
				row[fieldname if isinstance(row, dict) else index] = titles.get(name) or name
		titled_rows.append(row)
	return titled_rows


def get_link_names_by_doctype(columns, rows) -> dict[str, set]:
	"""Distinct non-empty values of every Link column, grouped by the doctype they link to."""
	return get_names_by_doctype(get_link_columns(columns or []), rows or [])


def get_link_columns(columns) -> list[tuple[int, str, str]]:
	"""Position, fieldname and linked doctype of every Link column."""
	return [
		(index, column["fieldname"], column["options"])
		for index, column in enumerate(columns)
		if isinstance(column, dict)
		and column.get("fieldtype") == "Link"
		and column.get("fieldname")
		and column.get("options")
	]


def get_names_by_doctype(link_columns, rows) -> dict[str, set]:
	names_by_doctype = {}
	for row in rows:
		for index, fieldname, doctype in link_columns:
			if name := get_row_value(row, fieldname, index):
				names_by_doctype.setdefault(doctype, set()).add(name)
	return names_by_doctype


def get_row_value(row, fieldname, index):
	"""Report rows are dicts, except in the prepared and export paths where they stay lists."""
	if isinstance(row, dict):
		return row.get(fieldname)
	return row[index] if index < len(row) else None
