# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.meta import get_field_precision
from frappe.tests.utils import FrappeTestCase, change_settings


class TestFieldPrecision(FrappeTestCase):
	def setUp(self):
		for currency, number_format in (("BHD", "#,###.###"), ("AED", "#,###.##")):
			if frappe.db.exists("Currency", currency):
				frappe.db.set_value("Currency", currency, "number_format", number_format)
			else:
				frappe.get_doc(
					doctype="Currency", currency_name=currency, number_format=number_format
				).insert()

		self.df = frappe._dict(fieldtype="Currency", fieldname="grand_total", options="currency")

	def invoice(self, currency):
		return frappe._dict(doctype="Sales Invoice", name=f"ACC-SINV-2024-{currency}", currency=currency)

	@change_settings(
		"System Settings",
		{"currency_precision": "", "number_format": "#,###.##", "use_number_format_from_currency": 1},
	)
	def test_precision_from_row_currency(self):
		self.assertEqual(get_field_precision(self.df, self.invoice("BHD")), 3)
		self.assertEqual(get_field_precision(self.df, self.invoice("AED")), 2)
		self.assertEqual(get_field_precision(self.df, None, currency="BHD"), 3)

	@change_settings(
		"System Settings",
		{"currency_precision": "", "number_format": "#,###.##", "use_number_format_from_currency": 0},
	)
	def test_global_number_format_when_currency_format_is_not_used(self):
		self.assertEqual(get_field_precision(self.df, self.invoice("BHD")), 2)

	@change_settings(
		"System Settings",
		{"currency_precision": 2, "number_format": "#,###.##", "use_number_format_from_currency": 1},
	)
	def test_currency_precision_takes_precedence(self):
		self.assertEqual(get_field_precision(self.df, self.invoice("BHD")), 2)
