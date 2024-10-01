import unittest
from contextlib import contextmanager

import frappe
from frappe.model.document import Document, read_only_document
from frappe.tests.utils import FrappeTestCase


class TestReadOnlyDocument(FrappeTestCase):
	def setUp(self):
		# Create a test document
		self.test_doc = frappe.get_doc({"doctype": "ToDo", "description": "Test ToDo"})
		self.test_doc.insert()

	def tearDown(self):
		# Delete the test document
		frappe.delete_doc("ToDo", self.test_doc.name)

	def test_read_only_save(self):
		with read_only_document():
			with self.assertRaises(frappe.DatabaseModificationError):
				self.test_doc.save()

	def test_read_only_insert(self):
		with read_only_document():
			with self.assertRaises(frappe.DatabaseModificationError):
				frappe.get_doc({"doctype": "ToDo", "description": "Another Test ToDo"}).insert()

	def test_read_only_delete(self):
		with read_only_document():
			with self.assertRaises(frappe.DatabaseModificationError):
				self.test_doc.delete()

	def test_read_only_submit(self):
		with read_only_document():
			with self.assertRaises(frappe.DatabaseModificationError):
				self.test_doc.submit()

	def test_read_only_cancel(self):
		with read_only_document():
			with self.assertRaises(frappe.DatabaseModificationError):
				self.test_doc.cancel()

	def test_read_only_db_set(self):
		with read_only_document():
			with self.assertRaises(frappe.DatabaseModificationError):
				self.test_doc.db_set("status", "Closed")

	def test_read_only_nested_calls(self):
		def nested_save():
			self.test_doc.save()

		with read_only_document():
			with self.assertRaises(frappe.DatabaseModificationError):
				nested_save()

	def test_read_only_context_manager_restoration(self):
		original_save = Document.save

		with read_only_document():
			self.assertNotEqual(Document.save, original_save)

		self.assertEqual(Document.save, original_save)

	def test_read_only_multiple_documents(self):
		doc1 = frappe.get_doc({"doctype": "ToDo", "description": "Test ToDo 1"})
		doc2 = frappe.get_doc({"doctype": "ToDo", "description": "Test ToDo 2"})

		with read_only_document():
			with self.assertRaises(frappe.DatabaseModificationError):
				doc1.insert()
			with self.assertRaises(frappe.DatabaseModificationError):
				doc2.insert()

	def test_read_only_custom_method(self):
		class CustomDocument(Document):
			def custom_save(self):
				self.save()

		custom_doc = CustomDocument({"doctype": "ToDo", "description": "Custom Test ToDo"})

		with read_only_document():
			with self.assertRaises(frappe.DatabaseModificationError):
				custom_doc.custom_save()

	def test_read_only_exception_handling(self):
		@contextmanager
		def exception_raiser():
			raise Exception("Test exception")
			yield

		try:
			with read_only_document(), exception_raiser():
				pass
		except Exception:
			pass

		# Ensure methods are restored even if an exception occurs
		self.assertEqual(Document.save, self.test_doc.__class__.save)

	def test_read_only_nested_context_managers(self):
		original_save = Document.save

		with read_only_document():
			self.assertNotEqual(Document.save, original_save)

			with read_only_document():
				self.assertNotEqual(Document.save, original_save)

			self.assertNotEqual(Document.save, original_save)

		self.assertEqual(Document.save, original_save)

	def test_read_only_method_call_details(self):
		with read_only_document():
			with self.assertRaises(frappe.DatabaseModificationError) as cm:
				self.test_doc.save()

			self.assertIn("Cannot call save in read-only document mode", str(cm.exception))

	def test_read_only_does_not_affect_reads(self):
		with read_only_document():
			# These operations should not raise exceptions
			doc = frappe.get_doc("ToDo", self.test_doc.name)
			self.assertEqual(doc.description, "Test ToDo")

			docs = frappe.get_all("ToDo", filters={"name": self.test_doc.name})
			self.assertEqual(len(docs), 1)

	def test_read_only_with_new_document_instance(self):
		with read_only_document():
			new_doc = frappe.new_doc("ToDo")
			with self.assertRaises(frappe.DatabaseModificationError):
				new_doc.insert()
