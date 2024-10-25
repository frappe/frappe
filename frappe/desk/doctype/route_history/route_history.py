# Copyright (c) 2022, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.deferred_insert import deferred_insert as _deferred_insert
from frappe.model.document import Document


class RouteHistory(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		route: DF.Data | None
		user: DF.Link | None
	# end: auto-generated types

	@staticmethod
	def clear_old_logs(days: int = 30) -> None:
		from frappe.query_builder import Interval
		from frappe.query_builder.functions import Now

		table = frappe.qb.DocType("Route History")
		frappe.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))


@frappe.whitelist()
def deferred_insert(routes) -> None:
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
	return frappe.get_all(
		"Route History",
		fields=["route", "count(name) as count"],
		filters={"user": frappe.session.user},
		group_by="route",
		order_by="count desc",
		limit=5,
	)
