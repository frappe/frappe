# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests import IntegrationTestCase
from frappe.website.doctype.website_settings.website_settings import get_website_settings


class TestWebsiteSettings(IntegrationTestCase):
	def test_child_items_in_top_bar(self):
		ws = frappe.get_doc("Website Settings")
		ws.append(
			"top_bar_items",
			{"label": "Parent Item"},
		)
		ws.append(
			"top_bar_items",
			{"parent_label": "Parent Item", "label": "Child Item"},
		)
		ws.save()

		context = get_website_settings()

		for item in context.top_bar_items:
			if item.label == "Parent Item":
				self.assertEqual(item.child_items[0].label, "Child Item")
				break
		else:
			self.fail("Child items not found")

	def test_redirect_setups(self):
		ws = frappe.get_doc("Website Settings")

		ws.append("route_redirects", {"source": "/engineering/(*.)", "target": "/development/(*.)"})
		self.assertRaises(frappe.ValidationError, ws.validate)

	def test_indexing_refresh_token_is_stored_encrypted(self):
		ws = frappe.get_doc("Website Settings")
		ws.indexing_refresh_token_secret = "test-refresh-token"
		ws.save()

		self.assertNotEqual(
			frappe.db.get_single_value("Website Settings", "indexing_refresh_token_secret"),
			"test-refresh-token",
		)
		self.assertEqual(
			frappe.get_doc("Website Settings").get_password("indexing_refresh_token_secret"),
			"test-refresh-token",
		)

	def test_patch_moves_indexing_refresh_token_to_password_field(self):
		from frappe.patches.v17_0.encrypt_indexing_refresh_token import execute

		frappe.db.set_single_value("Website Settings", "indexing_refresh_token", "old-refresh-token")
		execute()
		execute()

		self.assertFalse(frappe.db.get_single_value("Website Settings", "indexing_refresh_token"))
		self.assertEqual(
			frappe.get_doc("Website Settings").get_password("indexing_refresh_token_secret"),
			"old-refresh-token",
		)
