from frappe.model.base_document import BaseDocument
from frappe.model.document import Document
from frappe.tests.utils import FrappeTestCase


class TestBaseDocument(FrappeTestCase):
	def test_docstatus(self):
		doc = BaseDocument({"docstatus": 0, "doctype": "ToDo"})
		self.assertTrue(doc.docstatus.is_draft())
		self.assertEqual(doc.docstatus, 0)

		doc.docstatus = 1
		self.assertTrue(doc.docstatus.is_submitted())
		self.assertEqual(doc.docstatus, 1)

		doc.docstatus = 2
		self.assertTrue(doc.docstatus.is_cancelled())
		self.assertEqual(doc.docstatus, 2)

	def test_super_document_init_sets_values(self):
		class LegacyVirtualToDo(Document):
			def load_from_db(self):
				super(Document, self).__init__(
					{"doctype": "ToDo", "name": self.name, "description": "legacy"}
				)

		with self.assertWarns(DeprecationWarning):
			doc = LegacyVirtualToDo("ToDo", "legacy-todo")

		self.assertEqual(doc.name, "legacy-todo")
		self.assertEqual(doc.description, "legacy")
