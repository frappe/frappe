# Copyright (c) 2017, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import os
import shutil
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import nowdate


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

	def test_render_preview_uses_hook_context(self):
		from frappe.printing.doctype.letter_head.letter_head import render_preview

		letter_head = frappe.new_doc("Letter Head")
		letter_head.letter_head_for = "DocType"
		letter_head.letter_head_name = "Preview Test"
		letter_head.module = "Core"
		letter_head.standard = "No"
		letter_head.source = "HTML"
		letter_head.content = (
			"<h1>{{ doc.company }}</h1>"
			"<div>{{ doc.doctype }}</div>"
			"<strong>{{ doc.name }}</strong>"
			"<time>{{ doc.posting_date }}</time>"
		)
		letter_head.insert()

		original_get_hooks = frappe.get_hooks

		def get_hooks(hook_name=None, *args, **kwargs):
			if hook_name == "get_letter_head_preview_context":
				return [f"{__name__}.get_test_letter_head_preview_context"]
			return original_get_hooks(hook_name, *args, **kwargs)

		with patch("frappe.get_hooks", side_effect=get_hooks):
			preview = render_preview(letter_head.name, "content")

		self.assertNotIn("{{", preview)
		self.assertIn("Test Company", preview)
		self.assertIn("Sales Invoice", preview)
		self.assertIn("PREVIEW", preview)
		self.assertIn(nowdate(), preview)

	def test_rendering_modified_content_requires_write_permission(self):
		from frappe.printing.doctype.letter_head.letter_head import render_preview

		letter_head = frappe.new_doc("Letter Head")
		letter_head.letter_head_for = "DocType"
		letter_head.letter_head_name = "Preview Permission Test"
		letter_head.module = "Core"
		letter_head.standard = "No"
		letter_head.source = "HTML"
		letter_head.content = "<p>Stored content</p>"
		letter_head.insert()

		with patch.object(letter_head.__class__, "check_permission") as check_permission:
			render_preview(letter_head.name, "content", "<p>Modified content</p>")

		check_permission.assert_any_call("read")
		check_permission.assert_any_call("write")


def get_test_letter_head_preview_context(_doc):
	return {"doctype": "Sales Invoice", "company": "Test Company"}
