import frappe
from frappe import format
from frappe.tests import IntegrationTestCase
from frappe.utils.formatters import format_value


class TestFormatter(IntegrationTestCase):
	def test_currency_formatting(self):
		df = frappe._dict({"fieldname": "amount", "fieldtype": "Currency", "options": "currency"})

		doc = frappe._dict({"amount": 5})
		frappe.db.set_default("currency", "INR")

		# if currency field is not passed then default currency should be used.
		self.assertEqual(format(100000, df, doc, format="#,###.##"), "₹ 100,000.00")

		doc.currency = "USD"
		self.assertEqual(format(100000, df, doc, format="#,###.##"), "$ 100,000.00")

		frappe.db.set_default("currency", None)

	def test_safe_formatting(self):
		"""Test that in certain field types, the values are escaped."""
		payload = "<script>alert('testing')</script>"
		sanitized_payload = "&lt;script&gt;alert(&apos;testing&apos;)&lt;/script&gt;"

		data_df = frappe._dict({"fieldname": "book_name", "fieldtype": "Data"})
		self.assertEqual(format_value(payload, data_df), sanitized_payload)

		text_df = frappe._dict({"fieldname": "book_description", "fieldtype": "Text"})
		self.assertEqual(format_value(payload, text_df), sanitized_payload)

		html_df = frappe._dict({"fieldname": "book_title", "fieldtype": "HTML Editor"})
		self.assertEqual(format_value(payload, html_df), payload)

		editor_df = frappe._dict({"fieldtype": "Text Editor"})
		formatted_editor = format_value("<b>Bold</b>", editor_df)
		self.assertEqual(formatted_editor, "<div class='ql-snow'><b>Bold</b></div>")

		ltext_df = frappe._dict({"fieldname": "book_long_description", "fieldtype": "Long Text"})
		self.assertEqual(format_value(payload, ltext_df), sanitized_payload)

		select_df = frappe._dict({"fieldtype": "Select", "parent": "Task"})
		value = "Open"
		self.assertEqual(format_value(value, select_df), "Open")
		self.assertEqual(format_value(payload, select_df), sanitized_payload)

		link_df = frappe._dict({"fieldtype": "Link", "options": "User"})
		self.assertEqual(format_value(payload, link_df, doc=None), sanitized_payload)
		doc = frappe._dict({"__link_titles": {"User::attacker@example.com": "<svg onload=alert(1)>"}})
		formatted = format_value("attacker@example.com", link_df, doc)
		self.assertIn("&lt;svg", formatted)

		self.assertEqual(format_value(payload, df=None), sanitized_payload)
