# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Pure projection of Navigation Sections into the sidebar a client renders."""

from frappe.desk.doctype.navigation_item.navigation_item import DOCTYPE, LINK, VIEW
from frappe.desk.doctype.navigation_item.routes import doctype_route


def build_sidebar(sections, views, readable_doctypes, targets):
	"""Project sections and their ordered rows into `[{label, items: [...]}]`."""
	return [
		{
			"name": section["name"],
			"label": section["label"],
			"user": section.get("user") or "",
			"hidden": 1 if section.get("hidden") else 0,
			"items": placed_items(own_rows(section), views, readable_doctypes, targets),
		}
		for section in sections
	]


def own_rows(section):
	"""The section's rows, each marked with whether it is the caller's alone."""
	rows = section.get("items") or []
	return [{**row, "own": 1} for row in rows] if section.get("user") else rows


def placed_items(rows, views, readable_doctypes, targets):
	"""The section's rows as the client draws them, hidden ones carried with their flag."""
	items = (build_item(row, views, readable_doctypes, targets) for row in rows)
	return [item for item in items if item]


def build_item(row, views, readable_doctypes, targets):
	"""One row as the client draws it, or `None` for one pointing at something the caller cannot reach."""
	if item_type(row) == VIEW:
		view = views.get(str(row.get("view")))
		return item_payload(row, view, "") if view else None

	if item_type(row) == DOCTYPE:
		doctype = row.get("dt")
		return item_payload(row, None, doctype_route(doctype)) if doctype in readable_doctypes else None

	if item_type(row) == LINK:
		return item_payload(row, None, row.get("url") or "")

	target = targets.get(row.get("name"))
	return item_payload(row, None, target) if target else None


def item_type(row):
	"""A row's type, defaulting to `view` for one carrying none."""
	return row.get("type") or VIEW


def item_payload(row, view, url):
	"""One item for the client: the row's own label and icon win, falling back to the view's."""
	view = view or {}
	return {
		"name": row.get("name"),
		"type": item_type(row),
		"label": row.get("label") or view.get("label") or "",
		"icon": row.get("icon") or view.get("icon") or "",
		"dt": (row.get("dt") if item_type(row) == DOCTYPE else "") or "",
		"url": url or "",
		"new_tab": 1 if row.get("new_tab") else 0,
		"hidden": 1 if row.get("hidden") else 0,
		"own": 1 if row.get("own") else 0,
		"view": view or None,
	}
