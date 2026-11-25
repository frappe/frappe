from unittest.mock import patch

import frappe
from frappe.deferred_insert import deferred_insert, queue_prefix, save_to_db
from frappe.tests import IntegrationTestCase


class TestDeferredInsert(IntegrationTestCase):
	def tearDown(self):
		frappe.cache.delete_value(f"{queue_prefix}Route History")
		super().tearDown()

	def test_deferred_insert(self):
		route_history = {"route": frappe.generate_hash(), "user": "Administrator"}
		deferred_insert("Route History", [route_history])

		save_to_db()
		self.assertTrue(frappe.db.exists("Route History", route_history))

		route_history = {"route": frappe.generate_hash(), "user": "Administrator"}
		deferred_insert("Route History", [route_history])
		frappe.clear_cache()  # deferred_insert cache keys are supposed to be persistent
		save_to_db()
		self.assertTrue(frappe.db.exists("Route History", route_history))

	def test_transient_database_failure_requeues_uncommitted_records(self):
		records = [
			{"route": f"retry-{index}-{frappe.generate_hash()}", "user": "Administrator"}
			for index in range(2)
		]
		deferred_insert("Route History", records)

		with (
			patch("frappe.deferred_insert.insert_record", side_effect=[True, frappe.QueryDeadlockError()]),
			self.assertRaises(frappe.QueryDeadlockError),
		):
			save_to_db()

		self.assertEqual(frappe.cache.llen(f"{queue_prefix}Route History"), 1)
		save_to_db()
		for record in records:
			self.assertTrue(frappe.db.exists("Route History", record))
