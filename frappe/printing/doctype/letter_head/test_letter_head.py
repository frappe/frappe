# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import os
import shutil

import frappe
from frappe.tests import IntegrationTestCase


class TestLetterHead(IntegrationTestCase):
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
