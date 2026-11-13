# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from frappe.desk.doctype.form_layout.app_layout import read_app_layouts
from frappe.desk.doctype.form_layout.form_layout import (
	FORM_LAYOUT_TYPES,
	get_layout_rows,
	get_meta_layout,
	get_quick_entry_layout,
	layout_type_refusal,
	opens_in_dialog,
	parse_layout,
	row_layouts,
)


def get_editor_layouts(doctype: str, custom: bool) -> dict[str, list[dict]]:
	"""Every layout of each type the DocType allows, site rows first, each with its `source`.

	After the site rows come the app's: its file, or else one entry that says what draws without rows.
	Design shows the app's layouts, so they are sent even when a site row hides them."""
	return {
		type: site_layouts(doctype, type)
		+ (app_layouts(doctype, type) or [empty_layout(doctype, type, custom)])
		for type in FORM_LAYOUT_TYPES
		if not layout_type_refusal(doctype, type)
	}


def site_layouts(doctype: str, type: str) -> list[dict]:
	rows = get_layout_rows(doctype, type)
	return [
		{**layout, "app": row.app, "source": "site"}
		for row, layout in zip(rows, row_layouts(rows, doctype, type), strict=True)
	]


def app_layouts(doctype: str, type: str) -> list[dict]:
	found = read_app_layouts(doctype, type)
	return [
		{
			"name": None,
			"title": entry.title,
			"condition": entry.condition,
			"layout": parse_layout(entry.layout),
			"omitted": list(entry.omitted),
			"size": entry.size,
			"source": "app",
		}
		for entry in (found.entries if found else ())
	]


def empty_layout(doctype: str, type: str, custom: bool) -> dict:
	source, layout = empty_source(doctype, type, custom)
	return {"name": None, "title": None, "condition": None, "layout": layout, "omitted": [], "source": source}


def empty_source(doctype: str, type: str, custom: bool) -> tuple[str, list | None]:
	"""Design reads the fallback without site custom fields; Customize reads it with them."""
	if type == "Details":
		return "fallback", get_meta_layout(doctype, custom=custom)
	if type == "New Record":
		return "same as Details", None
	if type == "Quick Entry" and opens_in_dialog(doctype, []):
		return "fallback", get_quick_entry_layout(doctype, custom=custom)
	return "none", None
