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
	if title_field == "name" or not frappe.has_permission(doctype, "select"):
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
		titles.update({str(row.name): row.get(title_field) for row in rows})
	return titles


def get_permitted_link_titles(doctype: str, names: set[str]) -> dict[str, str]:
	"""Titles of `names` the user may see, keyed by document name."""
	title_field = get_link_title_field(doctype)
	return get_link_titles(doctype, title_field, names) if title_field else {}


def get_doc_link_titles(doc) -> dict[str, str]:
	"""Titles for the Link and Dynamic Link values of `doc` and its rows, keyed `doctype::name`."""
	link_titles = {}
	for doctype, names in get_link_values_by_doctype(doc).items():
		titles = get_permitted_link_titles(doctype, names)
		link_titles.update({f"{doctype}::{name}": titles.get(name) or name for name in names})
	return link_titles


def get_link_values_by_doctype(doc) -> dict[str, set]:
	"""Link and Dynamic Link values of `doc` and its rows, grouped by linked doctypes that show titles."""
	values_by_doctype = {}
	for row in [doc, *doc.get_all_children(include_computed=True)]:
		meta = frappe.get_meta(row.doctype)
		for field in meta.get_link_fields() + meta.get_dynamic_link_fields():
			if not (value := row.get(field.fieldname)):
				continue

			doctype = field.options if field.fieldtype == "Link" else row.get(field.options)
			link_meta = frappe.get_meta(doctype) if doctype else None
			if link_meta and link_meta.title_field and link_meta.show_title_field_in_link:
				values_by_doctype.setdefault(doctype, set()).add(value)

	return values_by_doctype


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
		for name, title in get_permitted_link_titles(doctype, names).items():
			titles[f"{doctype}::{name}"] = title
	return titles


def get_link_names_by_doctype(columns, rows) -> dict[str, set]:
	"""Distinct non-empty values of every Link column, grouped by the doctype they link to."""
	link_columns = [
		(index, column["fieldname"], column["options"])
		for index, column in enumerate(columns)
		if isinstance(column, dict)
		and column.get("fieldtype") == "Link"
		and column.get("fieldname")
		and column.get("options")
	]

	names_by_doctype = {}
	for row in rows:
		for index, fieldname, doctype in link_columns:
			# report rows are dicts, except in the prepared report path where they stay lists
			if isinstance(row, dict):
				name = row.get(fieldname)
			else:
				name = row[index] if index < len(row) else None
			if name:
				names_by_doctype.setdefault(doctype, set()).add(name)
	return names_by_doctype
