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

	def test_operations_on_locked_documents(self):
		todo = frappe.get_doc(dict(doctype="ToDo", description="testing operations")).insert()
		todo.lock()

		with self.assertRaises(frappe.DocumentLockedError):
			todo.description = "Random"
			todo.save()

		# Checking for persistant locks across all instances.
		doc = frappe.get_doc("ToDo", todo.name)
		self.assertEqual(doc.is_locked, True)

		with self.assertRaises(frappe.DocumentLockedError):
			doc.description = "Random"
			doc.save()

		doc.unlock()
		self.assertEqual(doc.is_locked, False)
		self.assertEqual(todo.is_locked, False)
