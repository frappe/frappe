# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.core.doctype.custom_icon.custom_icon import clear_symbol_cache, get_symbols, to_symbol
from frappe.tests import IntegrationTestCase

SAFE_SVG = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><circle cx="8" cy="8" r="6" fill="currentColor"></circle></svg>'
LUCIDE_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 3h18"></path></svg>'


class TestCustomIcon(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()
		# the cache outlives the rolled back transaction
		clear_symbol_cache()

	def test_safe_svg_is_kept(self):
		icon = frappe.get_doc({"doctype": "Custom Icon", "icon_name": "test-dot", "svg": SAFE_SVG}).insert()
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
			frappe.get_doc({"doctype": "Custom Icon", "icon_name": "test-empty", "svg": ""}).insert()

	def test_symbol_carries_the_id_and_drawing(self):
		symbol = to_symbol("test-dot", SAFE_SVG)
		self.assertIn('id="icon-test-dot"', symbol)
		self.assertIn('viewBox="0 0 16 16"', symbol)
		self.assertIn("<circle", symbol)
		self.assertTrue(symbol.startswith("<symbol"))
		self.assertNotIn("ns0:", symbol)

	def test_symbol_keeps_presentation_attributes_but_drops_sizing(self):
		symbol = to_symbol("test-line", LUCIDE_SVG)
		self.assertIn('stroke="currentColor"', symbol)
		self.assertIn('stroke-width="2"', symbol)
		self.assertIn('fill="none"', symbol)
		self.assertNotIn('width="24"', symbol)
		self.assertNotIn('height="24"', symbol)
		self.assertNotIn('stroke="none"', symbol)

	def test_names_that_carry_markup_are_rejected(self):
		# `<` and `>` never reach validate, since document naming rejects them first
		for icon_name in ('evil" onload="alert(1)', "<img src=x>", "spaced name", "quote'name"):
			with self.assertRaises((frappe.ValidationError, frappe.NameError)):
				frappe.get_doc({"doctype": "Custom Icon", "icon_name": icon_name, "svg": SAFE_SVG}).insert()

	def test_symbol_without_a_stroke_opts_out_of_the_desk_stroke(self):
		self.assertIn('stroke="none"', to_symbol("test-dot", SAFE_SVG))

	def test_saved_icons_reach_the_sprite(self):
		frappe.get_doc({"doctype": "Custom Icon", "icon_name": "test-dot", "svg": SAFE_SVG}).insert()
		symbols = get_symbols()
		self.assertIn("test-dot", [symbol["name"] for symbol in symbols])

	def test_deleting_an_icon_drops_it_from_the_sprite(self):
		icon = frappe.get_doc({"doctype": "Custom Icon", "icon_name": "test-dot", "svg": SAFE_SVG}).insert()
		get_symbols()
		icon.delete()
		self.assertNotIn("test-dot", [symbol["name"] for symbol in get_symbols()])
