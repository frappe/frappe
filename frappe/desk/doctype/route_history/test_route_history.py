# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.desk.doctype.route_history.route_history import (
	MAX_ROUTE_LENGTH,
	MAX_ROUTES_PER_REQUEST,
	deferred_insert,
)
from frappe.tests import IntegrationTestCase

EMAIL = "route.history.tester@example.com"


class TestRouteHistory(IntegrationTestCase):
	def setUp(self):
		if not frappe.db.exists("User", EMAIL):
			frappe.get_doc(
				{
					"doctype": "User",
					"email": EMAIL,
					"first_name": "Route History",
					"user_type": "Website User",
					"send_welcome_email": 0,
				}
			).insert()
		frappe.set_user(EMAIL)
		self.addCleanup(frappe.set_user, "Administrator")

	def _queued_records(self, routes):
		with patch("frappe.desk.doctype.route_history.route_history._deferred_insert") as queue:
			deferred_insert(routes)
		doctype, records = queue.call_args.args
		self.assertEqual(doctype, "Route History")
		return records

	def test_routes_are_queued_for_session_user(self):
		routes = [{"route": f"List/ToDo/{i}", "creation": "2026-01-01 00:00:00"} for i in range(3)]

		records = self._queued_records(frappe.as_json(routes))

		self.assertEqual([r["route"] for r in records], [r["route"] for r in routes])
		self.assertEqual({r["user"] for r in records}, {EMAIL})

	def test_oversized_batch_keeps_latest_routes(self):
		total = MAX_ROUTES_PER_REQUEST * 5
		routes = [{"route": f"Form/ToDo/{i}", "creation": "2026-01-01 00:00:00"} for i in range(total)]

		records = self._queued_records(routes)

		self.assertEqual(
			[r["route"] for r in records],
			[r["route"] for r in routes[-MAX_ROUTES_PER_REQUEST:]],
		)

	def test_route_longer_than_field_is_skipped(self):
		routes = [
			{"route": "x" * (MAX_ROUTE_LENGTH + 1), "creation": "2026-01-01 00:00:00"},
			{"route": "x" * MAX_ROUTE_LENGTH, "creation": "2026-01-01 00:00:00"},
		]

		records = self._queued_records(routes)

		self.assertEqual([r["route"] for r in records], ["x" * MAX_ROUTE_LENGTH])

	def test_client_creation_is_not_queued(self):
		records = self._queued_records([{"route": "List/ToDo/Report/Open", "creation": "x" * 10_000}])

		self.assertNotIn("creation", records[0])
