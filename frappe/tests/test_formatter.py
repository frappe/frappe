import frappe
from frappe import format
from frappe.tests.utils import FrappeTestCase


class TestFormatter(FrappeTestCase):
	def test_currency_formatting(self):
		df = frappe.attrdict({"fieldname": "amount", "fieldtype": "Currency", "options": "currency"})

		doc = frappe.attrdict({"amount": 5})
		frappe.db.set_default("currency", "INR")

		# if currency field is not passed then default currency should be used.
		self.assertEqual(format(100000, df, doc, format="#,###.##"), "₹ 100,000.00")

		doc.currency = "USD"
		self.assertEqual(format(100000, df, doc, format="#,###.##"), "$ 100,000.00")

		frappe.db.set_default("currency", None)
