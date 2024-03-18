import frappe
from frappe import format
from frappe.tests.utils import FrappeTestCase


class TestFormatter(FrappeTestCase):
	def test_currency_formatting(self):
		df = frappe._dict({"fieldname": "amount", "fieldtype": "Currency", "options": "currency"})

		doc = frappe._dict({"amount": 5})
		frappe.db.set_default("currency", "INR")

		# if currency field is not passed then default currency should be used.
		self.assertEqual(format(100000, df, doc, format="#,###.##"), "₹ 100,000.00")

		doc.currency = "USD"
		self.assertEqual(format(100000, df, doc, format="#,###.##"), "$ 100,000.00")

		frappe.db.set_default("currency", None)

	def test_duration_formatting(self):
		self.assertEqual(format(1, "Duration"), "1s")
		self.assertEqual(format(60, "Duration"), "1m")
		self.assertEqual(format(3600, "Duration"), "1h")
		self.assertEqual(format(24 * 3600, "Duration"), "1d")

		try:
			frappe.local.lang = "fr"
			self.assertEqual(format(24 * 3600, "Duration"), "1j")
		finally:
			frappe.local.lang = "en"
