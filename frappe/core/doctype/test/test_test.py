import json
import os

import frappe
from frappe.core.doctype.test.test import DATA_FILE
from frappe.core.doctype.test.test import test as VirtDocType
from frappe.desk.form.save import savedocs
from frappe.tests.utils import FrappeTestCase


class Testtest(FrappeTestCase):
	def tearDown(self):
		if os.path.exists(DATA_FILE):
			os.remove(DATA_FILE)

	def test_insert_update_and_load_from_desk(self):
		"""Insert, update, reload and assert changes"""

		frappe.response.docs = []
		doc = json.dumps(
			{
				"docstatus": 0,
				"doctype": "test",
				"name": "new-test-1",
				"__islocal": 1,
				"__unsaved": 1,
				"owner": "Administrator",
				"test": "Original Data",
			}
		)
		savedocs(doc, "Save")

		docname = frappe.response.docs[0]["name"]

		doc = frappe.get_doc("test", docname)
		doc.test = "New Data"

		savedocs(doc.as_json(), "Save")

		doc.reload()
		self.assertEqual(doc.test, "New Data")

	def test_multiple_doc_insert_and_get_list(self):
		doc1 = frappe.get_doc(doctype="test", test="first").insert()
		doc2 = frappe.get_doc(doctype="test", test="second").insert()

		docs = {doc1.name, doc2.name}

		doc2.reload()
		doc1.reload()
		updated_docs = {doc1.name, doc2.name}
		self.assertEqual(docs, updated_docs)

		listed_docs = {d.name for d in VirtDocType.get_list({})}
		self.assertEqual(docs, listed_docs)

	def test_get_count(self):
		args = {"doctype": "test", "filters": [], "fields": []}
		self.assertIsInstance(VirtDocType.get_count(args), int)

	def test_delete_doc(self):
		doc = frappe.get_doc(doctype="test", test="data").insert()

		frappe.delete_doc(doc.doctype, doc.name)

		listed_docs = {d.name for d in VirtDocType.get_list({})}
		self.assertNotIn(doc.name, listed_docs)
