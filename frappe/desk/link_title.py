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
