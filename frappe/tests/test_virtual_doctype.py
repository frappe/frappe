import json
import os
from unittest.mock import patch

import frappe
import frappe.modules.utils
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.desk.form.save import savedocs
from frappe.model.document import Document
from frappe.model.virtual_doctype import validate_controller
from frappe.tests import IntegrationTestCase

TEST_DOCTYPE_NAME = "VirtualDoctypeTest"
TEST_CHILD_DOCTYPE_NAME = "VirtualDoctypeTestChild"


class VirtualDoctypeTest(Document):
	"""This is a virtual doctype controller for test/demo purposes.

	- It uses a JSON file on disk as "backend".
	- Key is docname and value is the document itself.

	Example:
	{
	        "doc1": {"name": "doc1", ...}
	        "doc2": {"name": "doc2", ...}
	}
	"""

	DATA_FILE = "data_file.json"

	@staticmethod
	def get_current_data() -> dict[str, dict]:
		"""Read data from disk"""
		if not os.path.exists(VirtualDoctypeTest.DATA_FILE):
			return {}

		with open(VirtualDoctypeTest.DATA_FILE) as f:
			return json.load(f)

	@staticmethod
	def update_data(data: dict[str, dict]) -> None:
		"""Flush updated data to disk"""
		with open(VirtualDoctypeTest.DATA_FILE, "w+") as data_file:
			json.dump(data, data_file)

	def db_insert(self, *args, **kwargs):
		d = self.get_valid_dict(convert_dates_to_str=True)

		data = self.get_current_data()
		data[d.name] = d

		self.update_data(data)

	def load_from_db(self):
		data = self.get_current_data()
		d = data.get(self.name)
		super(Document, self).__init__(d)

	def db_update(self, *args, **kwargs):
		# For this example insert and update are same operation,
		# it might be  different for you
		self.db_insert(*args, **kwargs)

	def delete(self):
		data = self.get_current_data()
		data.pop(self.name, None)
		self.update_data(data)

	@staticmethod
	def get_list():
		data = VirtualDoctypeTest.get_current_data()
		return [frappe._dict(doc) for name, doc in data.items()]

	@staticmethod
	def get_count():
		data = VirtualDoctypeTest.get_current_data()
		return len(data)

	@staticmethod
	def get_stats():
		return {}


class TestVirtualDoctypes(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		frappe.flags.allow_doctype_export = True
		cls.addClassCleanup(frappe.flags.pop, "allow_doctype_export", None)

		cdt = new_doctype(name=TEST_CHILD_DOCTYPE_NAME, is_virtual=1, istable=1, custom=0).insert()
		vdt = new_doctype(
			name=TEST_DOCTYPE_NAME,
			is_virtual=1,
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
		cls.addClassCleanup(vdt.delete, force=True)
		cls.addClassCleanup(cdt.delete, force=True)

		patch_virtual_doc = patch(
			"frappe.controllers", new={frappe.local.site: {TEST_DOCTYPE_NAME: VirtualDoctypeTest}}
		)
		patch_virtual_doc.start()
		cls.addClassCleanup(patch_virtual_doc.stop)

	def tearDown(self):
		if os.path.exists(VirtualDoctypeTest.DATA_FILE):
			os.remove(VirtualDoctypeTest.DATA_FILE)

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
		self.assertEqual(doc.child_table[0].some_fieldname, "child1-field-value")

	def test_multiple_doc_insert_and_get_list(self):
		doc1 = frappe.new_doc(doctype=TEST_DOCTYPE_NAME)
		doc1.append("child_table", {"name": "first", "some_fieldname": "first-value"})
		doc1.insert()
		doc2 = frappe.new_doc(doctype=TEST_DOCTYPE_NAME)
		doc2.append("child_table", {"name": "second", "some_fieldname": "second-value"})
		doc2.insert()

		docs = {doc1.name, doc2.name}

		doc2.reload()
		doc1.reload()
		updated_docs = {doc1.name, doc2.name}
		self.assertEqual(docs, updated_docs)

		listed_docs = {d.name for d in VirtualDoctypeTest.get_list()}
		self.assertEqual(docs, listed_docs)

	def test_get_count(self):
		self.assertIsInstance(VirtualDoctypeTest.get_count(), int)

	def test_delete_doc(self):
		doc = frappe.get_doc(doctype=TEST_DOCTYPE_NAME).insert()

		frappe.delete_doc(doc.doctype, doc.name)

		listed_docs = {d.name for d in VirtualDoctypeTest.get_list()}
		self.assertNotIn(doc.name, listed_docs)

	def test_controller_validity(self):
		validate_controller(TEST_DOCTYPE_NAME)
		validate_controller(TEST_CHILD_DOCTYPE_NAME)
