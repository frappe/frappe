# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

"""Record counts for the views on a user's sidebar, cached briefly."""

import frappe
from frappe.desk.doctype.navigation_section.scope import Scope

COUNT_CACHE_TTL = 60
COUNT_FIELD = {"COUNT": "name", "as": "total"}


def view_counts(scope: Scope, refresh: bool = False) -> dict[str, int | None]:
	"""`{view name: count}` for the session user's sidebar views, from cache when warm."""
	key = cache_key(scope)
	if not refresh:
		cached = frappe.cache().get_value(key)
		if cached is not None:
			return cached

	counts = count_sidebar_views(scope)
	frappe.cache().set_value(key, counts, expires_in_sec=COUNT_CACHE_TTL)
	return counts


def count_sidebar_views(scope: Scope) -> dict[str, int | None]:
	from frappe.desk.doctype.navigation_section.navigation_section import resolved_sidebar

	_, placed = resolved_sidebar(scope)
	return {str(name): count_view(view) for name, view in placed.items()}


def count_view(view: dict) -> int | None:
	"""A view's record count, or `None` when its stored filters no longer apply."""
	try:
		return frappe.get_list(
			view["reference_doctype"],
			filters=frappe.parse_json(view.get("filters")) or [],
			fields=[COUNT_FIELD],
		)[0].total
	except Exception:
		return None


def cache_key(scope: Scope) -> str:
	return f"navigation_counts::{scope.app}::{scope.reference_doctype}::{frappe.session.user}"
