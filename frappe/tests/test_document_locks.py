# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.data import add_to_date, today


class TestDocumentLocks(FrappeTestCase):
	def test_locking(self):
		todo = frappe.get_doc(dict(doctype="ToDo", description="test")).insert()
		todo_1 = frappe.get_doc("ToDo", todo.name)

		todo.lock()
		self.assertRaises(frappe.DocumentLockedError, todo_1.lock)
		todo.unlock()

		todo_1.lock()
		self.assertRaises(frappe.DocumentLockedError, todo.lock)
		todo_1.unlock()

	def test_locks_auto_expiry(self):
		todo = frappe.get_doc(dict(doctype="ToDo", description=frappe.generate_hash())).insert()
		todo.lock()

		self.assertRaises(frappe.DocumentLockedError, todo.lock)

		with self.freeze_time(add_to_date(today(), days=3)):
			todo.lock()
