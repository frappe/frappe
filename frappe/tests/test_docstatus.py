from frappe.model.docstatus import DocStatus
from frappe.tests import IntegrationTestCase


class TestDocStatus(IntegrationTestCase):
	def test_draft(self) -> None:
		self.assertEqual(DocStatus(0), DocStatus.draft())

		self.assertTrue(DocStatus.draft().is_draft())
		self.assertFalse(DocStatus.draft().is_cancelled())
		self.assertFalse(DocStatus.draft().is_submitted())

	def test_submitted(self) -> None:
		self.assertEqual(DocStatus(1), DocStatus.submitted())

		self.assertFalse(DocStatus.submitted().is_draft())
		self.assertTrue(DocStatus.submitted().is_submitted())
		self.assertFalse(DocStatus.submitted().is_cancelled())

	def test_cancelled(self) -> None:
		self.assertEqual(DocStatus(2), DocStatus.cancelled())

		self.assertFalse(DocStatus.cancelled().is_draft())
		self.assertFalse(DocStatus.cancelled().is_submitted())
		self.assertTrue(DocStatus.cancelled().is_cancelled())
