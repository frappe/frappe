import os
import unittest

import frappe
from frappe.utils import add_to_date, now
from frappe.exceptions import DoesNotExistError

from random import choice, sample
from frappe.model.base_document import get_controller
from frappe.modules.utils import get_doc_path


class TestRenameDoc(unittest.TestCase):
	@classmethod
	def setUpClass(self):
		"""Setting Up data for the tests defined under TestRenameDoc"""
		# data generation: for base and merge tests
		self.available_documents = []
		self.test_doctype = "ToDo"

		for num in range(1, 5):
			doc = frappe.get_doc({
				"doctype": self.test_doctype,
				"date": add_to_date(now(), days=num),
				"description": "this is todo #{}".format(num),
			}).insert()
			self.available_documents.append(doc.name)

		#  data generation: for controllers tests
		self.doctype = frappe._dict({
			"old": "Test Rename Document Old",
			"new": "Test Rename Document New",
		})

		frappe.get_doc({
			"doctype": "DocType",
			"module": "Custom",
			"name": self.doctype.old,
			"custom": 0,
			"fields": [
				{"label": "Some Field", "fieldname": "some_fieldname", "fieldtype": "Data"}
			],
			"permissions": [{"role": "System Manager", "read": 1}],
		}).insert()

	@classmethod
	def tearDownClass(self):
		"""Deleting data generated for the tests defined under TestRenameDoc"""
		# delete the documents created
		for docname in self.available_documents:
			frappe.delete_doc(self.test_doctype, docname)

		for dt in self.doctype.values():
			if frappe.db.exists("DocType", dt):
				frappe.delete_doc("DocType", dt)
				frappe.db.sql_ddl(f"DROP TABLE `tab{dt}`")

	def test_rename_doc(self):
		"""Rename an existing document via frappe.rename_doc"""
		old_name = choice(self.available_documents)
		new_name = old_name + ".new"
		self.assertEqual(new_name, frappe.rename_doc(self.test_doctype, old_name, new_name, force=True))
		self.available_documents.remove(old_name)
		self.available_documents.append(new_name)

	def test_merging_docs(self):
		"""Merge two documents via frappe.rename_doc"""
		first_todo, second_todo = sample(self.available_documents, 2)

		second_todo_doc = frappe.get_doc(self.test_doctype, second_todo)
		second_todo_doc.priority = "High"
		second_todo_doc.save()

		merged_todo = frappe.rename_doc(
			self.test_doctype, first_todo, second_todo, merge=True, force=True
		)
		merged_todo_doc = frappe.get_doc(self.test_doctype, merged_todo)
		self.available_documents.remove(first_todo)

		with self.assertRaises(DoesNotExistError):
			frappe.get_doc(self.test_doctype, first_todo)

		self.assertEqual(merged_todo_doc.priority, second_todo_doc.priority)

	def test_rename_controllers(self):
		"""Rename doctypes with controller code paths"""
		# check if module exists exists;
		# if custom, get_controller will return Document class
		# if not custom, a different class will be returned
		self.assertNotEqual(get_controller(self.doctype.old), frappe.model.document.Document)

		old_doctype_path = get_doc_path("Custom", "DocType", self.doctype.old)

		# rename doc via wrapper API accessible via /desk
		frappe.rename_doc("DocType", self.doctype.old, self.doctype.new)

		# check if database and controllers are updated
		self.assertTrue(frappe.db.exists("DocType", self.doctype.new))
		self.assertFalse(frappe.db.exists("DocType", self.doctype.old))
		self.assertFalse(os.path.exists(old_doctype_path))
