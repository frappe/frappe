# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import os
import shutil

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.print_format import render_letterhead_for_print


class TestLetterHead(IntegrationTestCase):
	def test_rendered_letter_head_closes_tags_left_open_by_jinja(self):
		doc = frappe.new_doc("Letter Head")
		doc.letter_head_for = "Report"
		doc.letter_head_name = "Test Letter Head Conditional Logo"
		doc.content = '<div class="logo">{% if doc.company %}<img src="/files/logo.png"></div>{% endif %}'
		doc.footer = '<div class="address">{% if doc.company %}Mumbai</div>{% endif %}'
		doc.insert()

		with self.set_user("test@example.com"):
			rendered = render_letterhead_for_print(doc.name, {})

		self.assertEqual(rendered["header"], '<div class="logo"></div>')
		self.assertEqual(rendered["footer"], '<div class="address"></div>')

	def test_auto_image(self):
		doc = frappe.new_doc("Letter Head")
		doc.letter_head_for = "DocType"
		doc.letter_head_name = "Test Letter Head"
		doc.module = "Core"
		doc.standard = "No"
		doc.source = "Image"
		doc.image = "/public/test.png"
		doc.insert()

		# test if image is automatically set
		self.assertTrue(doc.image in doc.content)

	def test_export_letter_head(self):
		doc = frappe.new_doc("Letter Head")
		doc.letter_head_for = "DocType"
		doc.letter_head_name = "Test Letter Head Standard"
		doc.module = "Core"
		doc.standard = "No"
		doc.insert()

		doc.standard = "Yes"

		dev_mode_before = frappe.conf.developer_mode
		frappe.conf.developer_mode = True

		export_path = doc.export_letter_head()

		frappe.conf.developer_mode = dev_mode_before

		final_path = f"{export_path}.json"
		self.assertTrue(os.path.exists(final_path))

		dir_path = os.path.dirname(os.path.dirname(final_path))
		self.addCleanup(shutil.rmtree, dir_path)
