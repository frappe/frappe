# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json
import os
import re
import unittest
from pathlib import Path
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase


class TestPage(IntegrationTestCase):
	def test_naming(self):
		self.assertRaises(
			frappe.NameError,
			frappe.get_doc(doctype="Page", page_name="DocType", module="Core").insert,
		)

	@unittest.skipUnless(
		os.access(frappe.get_app_path("frappe"), os.W_OK), "Only run if frappe app paths is writable"
	)
	@patch.dict(frappe.conf, {"developer_mode": 1})
	def test_trashing(self):
		page = frappe.new_doc("Page", page_name=frappe.generate_hash(), module="Core").insert()

		page.delete()
		frappe.db.commit()

		module_path = frappe.get_module_path(page.module)
		dir_path = os.path.join(module_path, "page", frappe.scrub(page.name))

		self.assertFalse(os.path.exists(dir_path))

	@unittest.skipUnless(
		os.access(frappe.get_app_path("frappe"), os.W_OK), "Only run if frappe app paths is writable"
	)
	@patch.dict(frappe.conf, {"developer_mode": 1})
	def test_a_frappe_ui_page_is_scaffolded_as_an_island(self):
		page = self.make_page(type="Frappe UI")
		folder = page.get_folder_path()
		base = frappe.scrub(page.name)

		# The component and the entry that loads it, and no page script: an
		# island draws the whole page, so a script would only fight it.
		self.assertTrue(os.path.exists(os.path.join(folder, f"{base}.vue")))
		self.assertTrue(os.path.exists(os.path.join(folder, f"{base}.island.js")))
		self.assertFalse(os.path.exists(os.path.join(folder, f"{base}.js")))

		entry = open(os.path.join(folder, f"{base}.island.js")).read()
		self.assertIn(f'import Page from "./{base}.vue"', entry)
		self.assertIn("mountVueIsland", entry)

	@unittest.skipUnless(
		os.access(frappe.get_app_path("frappe"), os.W_OK), "Only run if frappe app paths is writable"
	)
	@patch.dict(frappe.conf, {"developer_mode": 1})
	def test_a_page_of_no_type_is_scaffolded_as_a_script(self):
		page = self.make_page()
		folder = page.get_folder_path()
		base = frappe.scrub(page.name)

		self.assertTrue(os.path.exists(os.path.join(folder, f"{base}.js")))
		self.assertFalse(os.path.exists(os.path.join(folder, f"{base}.vue")))

	@unittest.skipUnless(
		os.access(frappe.get_app_path("frappe"), os.W_OK), "Only run if frappe app paths is writable"
	)
	@patch.dict(frappe.conf, {"developer_mode": 1})
	def test_a_frappe_ui_page_tells_desk_which_island_draws_it(self):
		page = self.make_page(type="Frappe UI")

		# Derived where the desk assets are, so an export never carries it: the
		# name encodes the app, and a committed copy of it would go stale.
		self.assertNotIn("island", page.as_dict())
		page.load_assets()
		self.assertEqual(page.as_dict()["island"], f"frappe.page.{page.name}")

	@unittest.skipUnless(
		os.access(frappe.get_app_path("frappe"), os.W_OK), "Only run if frappe app paths is writable"
	)
	@patch.dict(frappe.conf, {"developer_mode": 1})
	def test_a_frappe_ui_page_ships_no_script(self):
		page = self.make_page(type="Frappe UI")

		# A page script is eval'd as a classic script. An island entry is a
		# module, so shipping one would be a syntax error in the browser.
		page.load_assets()
		self.assertEqual(page.script, "")

	@unittest.skipUnless(
		os.access(frappe.get_app_path("frappe"), os.W_OK), "Only run if frappe app paths is writable"
	)
	@patch.dict(frappe.conf, {"developer_mode": 1})
	def test_a_title_is_encoded_for_the_scaffold_it_lands_in(self):
		# A title is data, and the scaffold writes it into source. Substituted
		# raw, the quote ends the JS string early and the page does not build.
		page = self.make_page(type="Frappe UI", title='Q1 "Sales" </script> <b>& co</b>')
		source = Path(page.get_folder_path(), f"{frappe.scrub(page.name)}.vue").read_text()

		literal = re.search(r"const title = (.+);", source).group(1)
		self.assertEqual(json.loads(literal), page.title)

		# It appears once, and the template renders it as text rather than markup.
		self.assertEqual(source.count(literal), 1)
		self.assertIn("{{ title }}", source)

		# The literal sits in a `<script setup>` block, which the SFC parser ends
		# at the first `</script>` it reads.
		self.assertEqual(source.count("<script"), 1)
		self.assertEqual(source.count("</script>"), 1)

	def make_page(self, **values):
		"""A standard Page, written to disk and removed when the case ends."""
		page = frappe.new_doc(
			"Page", page_name=frappe.generate_hash(), module="Core", standard="Yes", **values
		).insert()

		def remove():
			with patch.dict(frappe.conf, {"developer_mode": 1}):
				frappe.delete_doc("Page", page.name, force=True)

			# `on_trash` queues the folder removal with `after_commit`, and a test
			# rolls back rather than commits, so the hook never fires. These cases
			# write real files into the app, so remove the folder directly instead
			# of committing the whole transaction to make the hook run.
			page.delete_folder_with_contents()

		self.addCleanup(remove)
		return page
