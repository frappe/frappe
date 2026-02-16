# Copyright (c) 2024, Frappe Technologies and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase


class TestUserSavedListView(IntegrationTestCase):
	def setUp(self):
		# Clean up any existing test views
		frappe.db.delete("User Saved List View", {"view_name": ("like", "Test View%")})

	def tearDown(self):
		frappe.db.delete("User Saved List View", {"view_name": ("like", "Test View%")})

	def test_create_private_view(self):
		"""Test creating a private view"""
		view = frappe.get_doc({
			"doctype": "User Saved List View",
			"view_name": "Test View Private",
			"reference_doctype": "ToDo",
			"is_public": 0,
			"columns": '[{"fieldname": "description", "label": "Description"}]',
			"filters": '[["ToDo", "status", "=", "Open"]]',
			"sort_by": "creation",
			"sort_order": "desc",
		})
		view.insert()

		self.assertEqual(view.owner, frappe.session.user)
		self.assertEqual(view.is_public, 0)

	def test_create_public_view(self):
		"""Test creating a public view (requires System Manager)"""
		view = frappe.get_doc({
			"doctype": "User Saved List View",
			"view_name": "Test View Public",
			"reference_doctype": "ToDo",
			"is_public": 1,
			"columns": '[{"fieldname": "description", "label": "Description"}]',
		})
		view.insert()

		self.assertEqual(view.is_public, 1)

	def test_duplicate_view_name(self):
		"""Test that duplicate view names for same doctype and user are not allowed"""
		view1 = frappe.get_doc({
			"doctype": "User Saved List View",
			"view_name": "Test View Duplicate",
			"reference_doctype": "ToDo",
		})
		view1.insert()

		view2 = frappe.get_doc({
			"doctype": "User Saved List View",
			"view_name": "Test View Duplicate",
			"reference_doctype": "ToDo",
		})

		self.assertRaises(frappe.ValidationError, view2.insert)

	def test_get_views(self):
		"""Test getting views for a doctype"""
		from frappe.desk.doctype.user_saved_list_view.user_saved_list_view import get_views

		# Create private view
		frappe.get_doc({
			"doctype": "User Saved List View",
			"view_name": "Test View Get 1",
			"reference_doctype": "ToDo",
			"is_public": 0,
		}).insert()

		# Create public view
		frappe.get_doc({
			"doctype": "User Saved List View",
			"view_name": "Test View Get 2",
			"reference_doctype": "ToDo",
			"is_public": 1,
		}).insert()

		views = get_views("ToDo")

		private_names = [v["view_name"] for v in views["private"]]
		public_names = [v["view_name"] for v in views["public"]]

		self.assertIn("Test View Get 1", private_names)
		self.assertIn("Test View Get 2", public_names)

	def test_save_view(self):
		"""Test save_view API"""
		from frappe.desk.doctype.user_saved_list_view.user_saved_list_view import save_view
		import json

		result = save_view(
			doctype="ToDo",
			view_name="Test View Save",
			columns=json.dumps([{"fieldname": "description", "label": "Description"}]),
			filters=json.dumps([["ToDo", "status", "=", "Open"]]),
			sort_by="creation",
			sort_order="desc",
			settings=json.dumps({"disable_count": 1}),
			is_public=0,
		)

		self.assertTrue(result.get("name"))

		# Verify the view was created
		doc = frappe.get_doc("User Saved List View", result["name"])
		self.assertEqual(doc.view_name, "Test View Save")
		self.assertEqual(doc.disable_count, 1)
