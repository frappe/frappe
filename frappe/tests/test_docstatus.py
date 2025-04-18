from frappe.model.docstatus import DocStatus
from frappe.tests import IntegrationTestCase


class TestDocStatus(IntegrationTestCase):
	def test_draft(self):
		self.assertEqual(DocStatus(0), DocStatus.DRAFT)

		self.assertTrue(DocStatus.DRAFT.is_draft())
		self.assertFalse(DocStatus.DRAFT.is_cancelled())
		self.assertFalse(DocStatus.DRAFT.is_submitted())

	def test_submitted(self):
		self.assertEqual(DocStatus(1), DocStatus.SUBMITTED)

		self.assertFalse(DocStatus.SUBMITTED.is_draft())
		self.assertTrue(DocStatus.SUBMITTED.is_submitted())
		self.assertFalse(DocStatus.SUBMITTED.is_cancelled())

	def test_cancelled(self):
		self.assertEqual(DocStatus(2), DocStatus.CANCELLED)

		self.assertFalse(DocStatus.CANCELLED.is_draft())
		self.assertFalse(DocStatus.CANCELLED.is_submitted())
		self.assertTrue(DocStatus.CANCELLED.is_cancelled())
