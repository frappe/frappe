# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests.utils import FrappeTestCase


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
