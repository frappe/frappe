# Copyright (c) 2022, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.deferred_insert import deferred_insert as _deferred_insert
from frappe.model.document import Document
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count


class RouteHistory(Document):
	pass


def flush_old_route_records():
	"""Deletes all route records except last 500 records per user"""
	records_to_keep_limit = 500
	RouteHistory = DocType("Route History")

	users = (
		frappe.qb.from_(RouteHistory)
		.select(RouteHistory.user)
		.groupby(RouteHistory.user)
		.having(Count(RouteHistory.name) > records_to_keep_limit)
	).run(pluck=True)

	for user in users:
		last_record_to_keep = frappe.get_all(
			"Route History",
			filters={"user": user},
			limit_start=500,
			fields=["modified"],
			order_by="modified desc",
			limit=1,
		)

		frappe.db.delete(
			"Route History",
			{"modified": ("<=", last_record_to_keep[0].modified), "user": user},
		)


@frappe.whitelist()
def deferred_insert(routes):
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
