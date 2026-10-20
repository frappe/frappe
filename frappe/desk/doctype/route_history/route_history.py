# Copyright (c) 2022, Frappe Technologies and contributors
# License: MIT. See LICENSE

from typing import Any

import frappe
from frappe.deferred_insert import deferred_insert as _deferred_insert
<<<<<<< HEAD
from frappe.model.document import Document
=======
from frappe.utils import cstr
from frappe.utils.logging import get_log_db, log_cutoff, log_table
from frappe.utils.sqlite_document import SQLiteLogDocument
>>>>>>> b0823c1 (fix(route-history): limit routes accepted per request)


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
	def clear_old_logs(days=30):
		from frappe.query_builder import Interval
		from frappe.query_builder.functions import Now

		table = frappe.qb.DocType("Route History")
		frappe.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))


MAX_ROUTES_PER_REQUEST = 100
MAX_ROUTE_LENGTH = 140


@frappe.whitelist()
def deferred_insert(routes: str | list[dict[str, Any]]):
	routes = [
		{
			"user": frappe.session.user,
			"route": route.get("route"),
		}
		for route in frappe.parse_json(routes)[-MAX_ROUTES_PER_REQUEST:]
		if len(cstr(route.get("route"))) <= MAX_ROUTE_LENGTH
	]

	_deferred_insert("Route History", routes)


@frappe.whitelist()
def frequently_visited_links():
	return frappe.get_all(
		"Route History",
		fields=["route", {"COUNT": "name", "as": "count"}],
		filters={"user": frappe.session.user},
		group_by="route",
		order_by="count desc",
		limit=5,
	)
