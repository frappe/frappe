import frappe
from frappe.deferred_insert import deferred_insert, save_to_db
from frappe.tests.utils import FrappeTestCase


class TestDeferredInsert(FrappeTestCase):
	def test_deferred_insert(self):
		route_history = {"route": frappe.generate_hash(), "user": "Administrator"}
		deferred_insert("Route History", [route_history])

		save_to_db()
		self.assertTrue(frappe.db.exists("Route History", route_history))
