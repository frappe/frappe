# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import json

import frappe
from frappe.deferred_insert import deferred_insert as _deferred_insert
from frappe.model.document import Document


class RouteHistory(Document):
	pass


def flush_old_route_records():
	"""Deletes all route records except last 500 records per user"""

	records_to_keep_limit = 500
	users = frappe.db.sql(
		"""
		SELECT `user`
		FROM `tabRoute History`
		GROUP BY `user`
		HAVING count(`name`) > %(limit)s
	""",
		{"limit": records_to_keep_limit},
	)

	for user in users:
		user = user[0]
		last_record_to_keep = frappe.db.get_all(
			"Route History",
			filters={
				"user": user,
			},
			limit=1,
			limit_start=500,
			fields=["modified"],
			order_by="modified desc",
		)

		frappe.db.sql(
			"""
				DELETE
				FROM `tabRoute History`
				WHERE `modified` <= %(modified)s and `user`=%(modified)s
			""",
			{"modified": last_record_to_keep[0].modified, "user": user},
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

	_deferred_insert("Route History", json.dumps(routes))
