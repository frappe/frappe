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


def get_link_titles(
	doctype: str, title_field: str, names: set[str], *, ignore_user_permissions: bool = False
) -> dict[str, str]:
	"""Titles of the readable documents among `names`, keyed by document name."""
	titles = {}
	for names_batch in create_batch(list(names), TITLE_BATCH_SIZE):
		rows = frappe.get_list(
			doctype,
			filters={"name": ("in", names_batch)},
			fields=["name", title_field],
			limit=len(names_batch),
			ignore_user_permissions=ignore_user_permissions,
		)
		titles.update({row.name: row.get(title_field) for row in rows})
	return titles


def get_doc_link_titles(
	doc, with_children: bool = True, fallback_to_name: bool = False
) -> dict[str, str | None]:
	"""Titles of the documents that `doc` and, with `with_children`, its child rows link to, keyed `doctype::name`.

	Only doctypes that show titles in links. A missing document maps to None; with `fallback_to_name`,
	a missing document or an empty title maps to the name. One query per linked doctype and 500 names.
	Virtual doctypes and doctypes whose title field is virtual are left out. Doesn't check permissions.
	"""
	meta = frappe.get_meta(doc.doctype)
	rows = [(meta, doc)]
	if with_children:
		for field in meta.get_table_fields(include_computed=True):
			child_meta = frappe.get_meta(field.options)
			rows.extend((child_meta, row) for row in doc.get(field.fieldname) or [])

	names_by_doctype = {}
	for row_meta, row in rows:
		for field in row_meta.get_link_fields() + row_meta.get_dynamic_link_fields():
			if not (name := getattr(row, field.fieldname, None)):
				continue
			doctype = field.options if field.fieldtype == "Link" else row.get(field.options)
			if doctype:
				names_by_doctype.setdefault(doctype, set()).add(name)

	titles = {}
	for doctype, names in names_by_doctype.items():
		link_meta = frappe.get_meta(doctype)
		if not (link_meta.title_field and link_meta.show_title_field_in_link):
			continue

		title_df = link_meta.get_field(link_meta.title_field)
		if link_meta.is_virtual or (title_df and title_df.is_virtual):
			continue

		found = {}
		for names_batch in create_batch(list(names), TITLE_BATCH_SIZE):
			results = frappe.get_all(
				doctype,
				filters={"name": ("in", names_batch)},
				fields=["name", link_meta.title_field],
				as_list=True,
			)
			found.update((str(name), title) for name, title in results)

		for name in names:
			title = found.get(str(name))
			titles[f"{doctype}::{name}"] = (title or name) if fallback_to_name else title

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
	for (doctype, ignore_user_permissions), names in names_by_doctype.items():
		title_field = get_link_title_field(doctype)
		if not title_field:
			continue
		for name, title in get_link_titles(
			doctype, title_field, names, ignore_user_permissions=ignore_user_permissions
		).items():
			titles[f"{doctype}::{name}"] = title
	return titles


def get_link_names_by_doctype(columns, rows) -> dict[tuple[str, bool], set]:
	"""Distinct non-empty values of every Link column, grouped by the doctype they link to
	and whether the column ignores user permissions."""
	link_columns = [
		(index, column["fieldname"], (column["options"], bool(column.get("ignore_user_permissions"))))
		for index, column in enumerate(columns)
		if isinstance(column, dict)
		and column.get("fieldtype") == "Link"
		and column.get("fieldname")
		and column.get("options")
	]

	names_by_doctype = {}
	for row in rows:
		for index, fieldname, key in link_columns:
			# report rows are dicts, except in the prepared report path where they stay lists
			if isinstance(row, dict):
				name = row.get(fieldname)
			else:
				name = row[index] if index < len(row) else None
			if name:
				names_by_doctype.setdefault(key, set()).add(name)
	return names_by_doctype
