import frappe
from frappe.locale import get_date_format, get_locale_value
from frappe.tests import IntegrationTestCase


class TestLocale(IntegrationTestCase):
	def test_locale_value_without_language(self):
		lang = frappe.local.lang
		date_format = frappe.db.get_default("date_format")
		try:
			frappe.local.lang = None

			frappe.db.set_default("date_format", "dd-mm-yyyy")
			self.assertEqual(get_locale_value("date_format"), "dd-mm-yyyy")

			frappe.db.set_default("date_format", None)
			self.assertIsNone(get_locale_value("date_format"))
			self.assertEqual(get_date_format(), "yyyy-mm-dd")
		finally:
			frappe.db.set_default("date_format", date_format)
			frappe.local.lang = lang
