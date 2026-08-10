# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests import IntegrationTestCase

SAFE_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="currentColor"></circle></svg>'


class TestCustomIcon(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def test_safe_svg_is_kept(self):
		icon = frappe.get_doc(
			{"doctype": "Custom Icon", "icon_name": "test-dot", "svg": SAFE_SVG}
		).insert()
		self.assertIn("<circle", icon.svg)
		self.assertIn('fill="currentColor"', icon.svg)

	def test_scripts_and_handlers_are_stripped(self):
		icon = frappe.get_doc(
			{
				"doctype": "Custom Icon",
				"icon_name": "test-evil",
				"svg": '<svg viewBox="0 0 16 16" onload="alert(1)"><script>alert(1)</script><path d="M0 0h16v16H0z"/></svg>',
			}
		).insert()
		self.assertNotIn("script", icon.svg)
		self.assertNotIn("onload", icon.svg)
		self.assertIn("<path", icon.svg)

	def test_plain_html_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{"doctype": "Custom Icon", "icon_name": "test-html", "svg": "<div>not an icon</div>"}
			).insert()

	def test_trailing_content_after_svg_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{"doctype": "Custom Icon", "icon_name": "test-trailing", "svg": SAFE_SVG + "<svg></svg>"}
			).insert()

	def test_empty_svg_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{"doctype": "Custom Icon", "icon_name": "test-empty", "svg": ""}
			).insert()
