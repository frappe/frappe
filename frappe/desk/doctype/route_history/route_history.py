# Copyright (c) 2022, Frappe Technologies and contributors
# License: MIT. See LICENSE

from typing import Any

import frappe
from frappe.deferred_insert import deferred_insert as _deferred_insert
from frappe.model.document import Document


class RouteHistory(Document):
	_DOCTYPE_NAME = "Route History"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		route: DF.Data | None
		user: DF.Link | None
	# end: auto-generated types

	@staticmethod
	def clear_old_logs(days=30):
		from frappe.query_builder import Interval
		from frappe.query_builder.functions import Now

		table = frappe.qb.DocType("Route History")
		frappe.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))


@frappe.whitelist()
def deferred_insert(routes: str | list[dict[str, Any]]):
	routes = [
		{
			"user": frappe.session.user,
			"route": route.get("route"),
			"creation": route.get("creation"),
		}
		for route in frappe.parse_json(routes)
	]

	_deferred_insert("Route History", routes)


@frappe.whitelist()
def frequently_visited_links():
	from frappe.desk.desk_views import DeskViews

	# Fetch a larger candidate set since some entries may be filtered out
	candidates = frappe.get_all(
		"Route History",
		fields=["route", {"COUNT": "name", "as": "count"}],
		filters={"user": frappe.session.user},
		group_by="route",
		order_by="count desc",
		limit=25,
	)

	allowed_report_names = set(DeskViews.get_allowed_reports(cache=True).keys())
	result = []
	for link in candidates:
		if _is_permitted_link(link["route"], allowed_report_names):
			result.append(link)
		if len(result) == 5:
			break
	return result


def _is_permitted_link(route: str, allowed_report_names: set) -> bool:
	"""Filter Route History entries by report accessibility.

	Route History persists routes forever. When the user loses permission on
	the underlying report/doctype, the route stays in the table and would
	otherwise resurface as a "frequently visited" suggestion. Non-report
	routes (Form/List/etc.) pass through — their permissions are enforced
	when the route is followed.
	"""
	parts = route.split("/")
	# Query Report: "query-report/<name>"
	if len(parts) >= 2 and parts[0] == "query-report":
		return parts[1] in allowed_report_names
	# Report Builder: "List/<doctype>/Report/<name>"
	if len(parts) >= 4 and parts[0] == "List" and parts[2] == "Report":
		return parts[3] in allowed_report_names
	return True
