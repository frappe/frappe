import json
from unittest.mock import call, patch

import redis

import frappe
from frappe.core.doctype.error_log.error_log import flush_error_logs, get_queued_error_log_count
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

	def test_error_log_redis_failure_falls_back_to_database(self):
		record = {"method": "Error 1", "error": "Failed to deliver"}
		records = [record, {"method": "Error 2", "error": "Delivery timed out"}]
		for input_shape, payload, expected_records in (
			("dict", record, [record]),
			("list", records, records),
			("json_dict", json.dumps(record), [record]),
			("json_list", json.dumps(records), records),
		):
			with (
				self.subTest(input_shape=input_shape),
				patch.object(frappe.cache, "rpush", side_effect=redis.exceptions.ConnectionError),
				patch("frappe.deferred_insert.insert_record", return_value=True) as insert_record,
			):
				deferred_insert("Error Log", payload)
				self.assertEqual(
					insert_record.call_args_list,
					[call(expected_record, "Error Log") for expected_record in expected_records],
				)

	def test_save_to_db_for_single_doctype(self):
		route_history = {"route": frappe.generate_hash(), "user": "Administrator"}
		error_log = {"method": "Deferred error", "error": "Test traceback"}
		deferred_insert("Route History", route_history)
		deferred_insert("Error Log", error_log)

		self.assertEqual(get_queued_error_log_count(), 1)
		flush_error_logs()

		self.assertTrue(frappe.db.exists("Error Log", {"method": "Deferred error"}))
		self.assertEqual(get_queued_error_log_count(), 0)
		self.assertEqual(frappe.cache.llen(f"{queue_prefix}Route History"), 1)

		save_to_db(doctype="Route History")

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
			save_to_db(doctype="Route History")

		self.assertEqual(frappe.cache.llen(f"{queue_prefix}Route History"), 1)
		save_to_db(doctype="Route History")
		for record in records:
			self.assertTrue(frappe.db.exists("Route History", record))
