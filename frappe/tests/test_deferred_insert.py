import frappe
from frappe.core.doctype.error_log.error_log import flush_error_logs, get_queued_error_log_count
from frappe.deferred_insert import deferred_insert, queue_prefix, save_to_db
from frappe.tests import IntegrationTestCase


class TestDeferredInsert(IntegrationTestCase):
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
