# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Pure rules for where a Saved View sits: which sections hold it, and which views none holds."""


def placed_names(sections):
	"""Every view name any section holds."""
	rows = (row for section in sections for row in section.get("items") or [])
	return {str(row.get("view")) for row in rows if row.get("view")}


def unplaced_views(views, placed):
	"""The pool: views no section holds, in the order given."""
	return [view for view in views if str(view.get("name")) not in placed]


def without_view(rows, view):
	"""`rows` minus every row pointing at `view` — removing from a sidebar, not deleting."""
	wanted = str(view)
	return [row for row in rows if str(row.get("view")) != wanted]
