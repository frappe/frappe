import frappe
from frappe.deferred_insert import deferred_insert, save_to_db
from frappe.tests.utils import FrappeTestCase


class TestDeferredInsert(FrappeTestCase):
	def tearDown(self) -> None:
		frappe.set_user("Administrator")

	def test_deferred_insert(self):
		def insert_route_history(ignore_permissions=False):
			route_history = {"route": frappe.generate_hash(), "user": "Administrator"}
			deferred_insert("Route History", [route_history | {"ignore_permissions": ignore_permissions}])

			save_to_db()
			return route_history

		route_history = insert_route_history()
		self.assertTrue(frappe.db.exists("Route History", route_history))

		frappe.set_user("fakeuser@example.com")
		route_history = insert_route_history()
		self.assertFalse(frappe.db.exists("Route History", route_history))

		route_history = insert_route_history(ignore_permissions=True)
		self.assertTrue(frappe.db.exists("Route History", route_history))
