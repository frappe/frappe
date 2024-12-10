import frappe
from frappe import format
<<<<<<< HEAD
from frappe.tests.utils import FrappeTestCase


class TestFormatter(FrappeTestCase):
=======
from frappe.tests import IntegrationTestCase


class TestFormatter(IntegrationTestCase):
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	def test_currency_formatting(self):
		df = frappe._dict({"fieldname": "amount", "fieldtype": "Currency", "options": "currency"})

		doc = frappe._dict({"amount": 5})
		frappe.db.set_default("currency", "INR")

		# if currency field is not passed then default currency should be used.
		self.assertEqual(format(100000, df, doc, format="#,###.##"), "₹ 100,000.00")

		doc.currency = "USD"
		self.assertEqual(format(100000, df, doc, format="#,###.##"), "$ 100,000.00")

		frappe.db.set_default("currency", None)
