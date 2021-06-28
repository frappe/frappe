# -*- coding: utf-8 -*-
import frappe
from frappe import format
import unittest

class TestFormatter(unittest.TestCase):
	def test_currency_formatting(self):
		df = frappe._dict({
			'fieldname': 'amount',
			'fieldtype': 'Currency',
			'options': 'currency'
		})

		doc = frappe._dict({
			'amount': 5
		})
		frappe.db.set_default("currency", 'INR')

		# if currency field is not passed then default currency should be used.
		self.assertEqual(format(100, df, doc), '₹ 100.00')

		doc.currency = 'USD'
		self.assertEqual(format(100, df, doc), "$ 100.00")

		frappe.db.set_default("currency", None)

	def test_custom_currency_formatting(self):
		df = frappe._dict({
			'fieldname': 'amount',
			'fieldtype': 'Currency',
			'options': 'currency'
		})

		doc = frappe._dict({
			'amount': 5
		})
		frappe.db.set_default("currency", 'INR')

		# if currency field is not passed then default currency should be used.
		print("doc.currency")
		print(doc.currency)
		self.assertEqual(format(100000, df, doc, format="#,###.##"), '₹ 100,000.00')

		doc.currency = 'USD'
		self.assertEqual(format(100000, df, doc, format="#,###.##"), "$ 100,000.00")

		frappe.db.set_default("currency", None)
