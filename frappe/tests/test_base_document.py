import unittest

from frappe.model.base_document import BaseDocument


class TestBaseDocument(unittest.TestCase):
	def test_docstatus(self):
		doc = BaseDocument({"docstatus": 0})
		self.assertTrue(doc.docstatus.is_draft())
		self.assertEquals(doc.docstatus, 0)

		doc.docstatus = 1
		self.assertTrue(doc.docstatus.is_submitted())
		self.assertEquals(doc.docstatus, 1)

		doc.docstatus = 2
		self.assertTrue(doc.docstatus.is_cancelled())
		self.assertEquals(doc.docstatus, 2)
