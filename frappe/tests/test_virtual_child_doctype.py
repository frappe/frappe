import json
import os
from typing import ClassVar
from unittest.mock import patch

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.form.save import savedocs
from frappe.model.base_document import get_controller
from frappe.model.document import Document
from frappe.model.virtual_doctype import validate_controller
from frappe.tests import IntegrationTestCase
from frappe.utils import generate_hash

TEST_DOCTYPE_NAME = "DoctypeTest"
TEST_CHILD_DOCTYPE_NAME = "VirtualDocTypeAsChildTableTest"


class VirtualDocTypeAsChildTableTest(Document):
	"""This is a virtual doctype controller for test/demo purposes.

	- It uses a JSON file on disk as "backend".
	- Key is docname and value is the document itself.

	Example:
	{
					"doc1": {"name": "doc1", ...}
					"doc2": {"name": "doc2", ...}
	}
	"""

	data_store: ClassVar[list] = []

	@staticmethod
	def clear_data():
		VirtualDocTypeAsChildTableTest.data_store = []

	# Static methods for VirtualDoctype protocol
	@staticmethod
	def get_list(
		parent_doc=None, filters=None, fields=None, limit_start=0, limit_page_length=20, order_by=None
	):
		data = VirtualDocTypeAsChildTableTest.data_store

		if parent_doc:
			data = [d for d in data if d.get("parent") == parent_doc.name]

		if filters:
			for f_key, f_val in filters.items():
				if isinstance(f_val, (list | tuple)) and f_val[0] == "in":
					data = [d for d in data if d.get(f_key) in f_val[1]]
				else:
					data = [d for d in data if d.get(f_key) == f_val]

		# Sorting (simplified: assumes order_by is a field name, asc)
		if order_by:
			# Assuming order_by is in the format "field_name asc" or "field_name desc"
			# For simplicity, this example only handles "field_name" (ascending)
			# and ignores asc/desc. A more robust solution would parse this.
			sort_key = order_by.split(" ")[0]
			data = sorted(data, key=lambda x: x.get(sort_key, 0))

		# Pagination
		start = int(limit_start)
		length = int(limit_page_length)
		data = data[start : start + length]

		# Field selection
		if fields:
			# Ensure 'name' is always included if not explicitly asked for, as it's often expected
			if "name" not in fields and any("name" in d for d in data):
				# Make a copy to avoid modifying the input list
				_fields = fields[:]
				if isinstance(_fields, list) and "name" not in _fields:
					_fields.append("name")
			else:
				_fields = fields

			result = []
			for doc in data:
				filtered_doc = {}
				for field in _fields:
					if field in doc:
						filtered_doc[field] = doc[field]
				result.append(filtered_doc)
			return result
		else:
			# Return all fields if no specific fields are requested
			return data

	@staticmethod
	def get_count(parent_doc=None, filters=None):
		data = VirtualDocTypeAsChildTableTest.data_store

		if parent_doc:
			data = [d for d in data if d.get("parent") == parent_doc.name]

		if filters:
			for f_key, f_val in filters.items():
				if isinstance(f_val, (list | tuple)) and f_val[0] == "in":
					data = [d for d in data if d.get(f_key) in f_val[1]]
				else:
					data = [d for d in data if d.get(f_key) == f_val]

		return len(data)

	@staticmethod
	def get_stats():
		# Return a simple predefined dictionary
		return {}

	# Instance methods for VirtualDoctype protocol
	def db_insert(self, *args, **kwargs):
		if not self.name:
			if kwargs.get("name"):
				self.name = kwargs["name"]
			else:
				self.name = generate_hash(length=10)  # frappe.generate_hash() is not available here

		# Avoid circular references if _doc_before_save is present
		doc_dict = self.as_dict()
		if "_doc_before_save" in doc_dict:
			del doc_dict["_doc_before_save"]

		VirtualDocTypeAsChildTableTest.data_store.append(doc_dict)
		return self

	def load_from_db(self):
		if not self.name:
			raise frappe.IncompleteTableError("name")  # Or some other appropriate error

		record_data = None
		for record in VirtualDocTypeAsChildTableTest.data_store:
			if record.get("name") == self.name:
				record_data = record
				break

		if record_data:
			self.update(record_data)
			# self.set_new_name(self.name) # Not typically needed here as name is already set
			return self  # Ensure the method returns self as per some Document method expectations
		else:
			raise frappe.DoesNotExistError(f"{self.doctype} {self.name} not found")

	def db_update(self, *args, **kwargs):
		if not self.name:
			# Or handle as an error, but for tests, ensuring a name might be okay.
			raise NameError("Name must be set before update")

		record_exists = False
		for i, record in enumerate(VirtualDocTypeAsChildTableTest.data_store):
			if record.get("name") == self.name:
				# Avoid circular references if _doc_before_save is present
				doc_dict = self.as_dict()
				if "_doc_before_save" in doc_dict:
					del doc_dict["_doc_before_save"]
				VirtualDocTypeAsChildTableTest.data_store[i] = doc_dict
				record_exists = True
				break

		if not record_exists:
			# If record not found, effectively do an insert
			self.db_insert(*args, **kwargs)  # This will handle adding it to data_store

		return self

	def delete(self, *args, **kwargs):
		if not self.name:
			# Nothing to delete if name is not set
			return

		original_length = len(VirtualDocTypeAsChildTableTest.data_store)
		VirtualDocTypeAsChildTableTest.data_store = [
			record for record in VirtualDocTypeAsChildTableTest.data_store if record.get("name") != self.name
		]

		if len(VirtualDocTypeAsChildTableTest.data_store) == original_length:
			raise frappe.DoesNotExistError(f"{self.doctype} {self.name} not found for deletion")

		return self


class TestVirtualChildDoctypes(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		frappe.flags.allow_doctype_export = True
		cls.addClassCleanup(frappe.flags.pop, "allow_doctype_export", None)

		cdt = new_doctype(name=TEST_CHILD_DOCTYPE_NAME, is_virtual=1, istable=1, custom=0).insert()
		pdt = new_doctype(
			name=TEST_DOCTYPE_NAME,
			is_virtual=0,
			custom=0,
			fields=[
				{
					"label": "Child Table",
					"fieldname": "child_table",
					"fieldtype": "Table",
					"options": TEST_CHILD_DOCTYPE_NAME,
				}
			],
		).insert()
		cls.addClassCleanup(pdt.delete, force=True)
		cls.addClassCleanup(cdt.delete, force=True)

		patch_virtual_doc = patch(
			"frappe.controllers",
			new={frappe.local.site: {TEST_CHILD_DOCTYPE_NAME: VirtualDocTypeAsChildTableTest}},
		)
		patch_virtual_doc.start()
		cls.addClassCleanup(patch_virtual_doc.stop)

	def tearDown(self):
		VirtualDocTypeAsChildTableTest.clear_data()

	def test_insert_update_and_load_from_desk(self):
		"""Insert, update, reload and assert changes"""

		frappe.response.docs = []
		doc = json.dumps(
			{
				"docstatus": 0,
				"doctype": TEST_DOCTYPE_NAME,
				"name": "new-doctype-1",
				"__islocal": 1,
				"__unsaved": 1,
				"owner": "Administrator",
				TEST_DOCTYPE_NAME: "Original Data",
			}
		)
		savedocs(doc, "Save")

		docname = frappe.response.docs[0]["name"]

		doc = frappe.get_doc(TEST_DOCTYPE_NAME, docname)

		doc.update({"child_table": [{"name": "child-1", "some_fieldname": "child1-field-value"}]})

		savedocs(doc.as_json(), "Save")
		doc.reload()
		self.assertEqual(doc.child_table[0].name, "child-1")
		self.assertEqual(doc.child_table[0].some_fieldname, "child1-field-value")

	def test_multiple_doc_insert_and_get_list(self):
		doc1 = frappe.new_doc(doctype=TEST_DOCTYPE_NAME)
		doc1_child = {"name": "first", "some_fieldname": "first-value"}
		doc1.append("child_table", doc1_child)
		# If we don't set `set_child_names=False`, the child table will have its
		# name cleared and a new name generated for it...
		# Of course, by overriding and setting the name manually, there could be
		# clashes between different docs that use the same child name.
		doc1.insert(set_child_names=False)

		doc2 = frappe.new_doc(doctype=TEST_DOCTYPE_NAME)
		doc2_child = {"name": "second", "some_fieldname": "second-value"}
		doc2.append("child_table", doc2_child)
		doc2.insert(set_child_names=False)

		docs = {doc1.name, doc2.name}
		children = {doc1_child["name"], doc2_child["name"]}

		doc2.reload()
		doc1.reload()
		updated_docs = {doc1.name, doc2.name}
		updated_children = {doc1.child_table[0].name, doc2.child_table[0].name}
		self.assertEqual(docs, updated_docs)
		self.assertEqual(children, updated_children)

		listed_docs = {d.name for d in VirtualDocTypeAsChildTableTest.get_list()}
		self.assertEqual(children, listed_docs)

	def test_get_count(self):
		self.assertIsInstance(VirtualDocTypeAsChildTableTest.get_count(), int)

	def test_delete_doc(self):
		doc = frappe.get_doc(doctype=TEST_DOCTYPE_NAME).insert()

		frappe.delete_doc(doc.doctype, doc.name)

		listed_docs = {d.name for d in VirtualDocTypeAsChildTableTest.get_list()}
		self.assertNotIn(doc.name, listed_docs)

	def test_controller_validity(self):
		validate_controller(TEST_DOCTYPE_NAME)
		validate_controller(TEST_CHILD_DOCTYPE_NAME)
