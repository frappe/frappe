# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import frappe
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase
from frappe.utils.data import add_to_date, today


class TestDocumentLocks(FrappeTestCase):
	def test_locking(self):
		todo = frappe.get_doc(dict(doctype="ToDo", description="test")).insert()
=======
from frappe.tests import IntegrationTestCase
from frappe.utils.data import add_to_date, today


class TestDocumentLocks(IntegrationTestCase):
	def test_locking(self):
		todo = frappe.get_doc(doctype="ToDo", description="test").insert()
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		todo_1 = frappe.get_doc("ToDo", todo.name)

		todo.lock()
		self.assertRaises(frappe.DocumentLockedError, todo_1.lock)
		todo.unlock()

		todo_1.lock()
		self.assertRaises(frappe.DocumentLockedError, todo.lock)
		todo_1.unlock()

	def test_operations_on_locked_documents(self):
<<<<<<< HEAD
		todo = frappe.get_doc(dict(doctype="ToDo", description="testing operations")).insert()
=======
		todo = frappe.get_doc(doctype="ToDo", description="testing operations").insert()
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
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

	def test_locks_auto_expiry(self):
<<<<<<< HEAD
		todo = frappe.get_doc(dict(doctype="ToDo", description=frappe.generate_hash())).insert()
=======
		todo = frappe.get_doc(doctype="ToDo", description=frappe.generate_hash()).insert()
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		todo.lock()

		self.assertRaises(frappe.DocumentLockedError, todo.lock)

		with self.freeze_time(add_to_date(today(), days=3)):
			todo.lock()
