# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils.print_format import render_letterhead_for_print


class TestLetterHead(FrappeTestCase):
	def test_rendered_letter_head_closes_tags_left_open_by_jinja(self):
		doc = frappe.new_doc("Letter Head")
		doc.letter_head_name = "Test Letter Head Conditional Logo"
		doc.content = '<div class="logo">{% if doc.company %}<img src="/files/logo.png"></div>{% endif %}'
		doc.footer = '<div class="address">{% if doc.company %}Mumbai</div>{% endif %}'
		doc.insert()

		with self.set_user("test@example.com"):
			rendered = render_letterhead_for_print(doc.name, {})

		self.assertEqual(rendered["header"], '<div class="logo"></div>')
		self.assertEqual(rendered["footer"], '<div class="address"></div>')

	def test_auto_image(self):
		letter_head = frappe.get_doc(
			dict(doctype="Letter Head", letter_head_name="Test", source="Image", image="/public/test.png")
		).insert()

		# test if image is automatically set
		self.assertTrue(letter_head.image in letter_head.content)
