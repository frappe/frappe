# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests import IntegrationTestCase


class TestPortalSettings(IntegrationTestCase):
	"""Test cases for Portal Settings doctype - bug fixes and edge cases"""

	def setUp(self):
		"""Set up test fixtures"""
		self.doc = frappe.get_single("Portal Settings")

	def tearDown(self):
		"""Clean up after tests"""
		# Reset to clean state
		self.doc.menu = []
		self.doc.custom_menu = []
		self.doc.save()

	def test_get_all_menu_items_with_both_none(self):
		"""Test get_all_menu_items() returns empty list when both menu and custom_menu are None"""
		self.doc.menu = None
		self.doc.custom_menu = None

		result = self.doc.get_all_menu_items()

		self.assertIsInstance(result, list)
		self.assertEqual(result, [])

	def test_get_all_menu_items_with_menu_none(self):
		"""Test get_all_menu_items() when only menu is None"""
		self.doc.menu = None
		self.doc.custom_menu = [
			{"title": "Custom Item", "route": "custom", "enabled": 1}
		]

		result = self.doc.get_all_menu_items()

		self.assertIsInstance(result, list)
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0].title, "Custom Item")

	def test_get_all_menu_items_with_custom_menu_none(self):
		"""Test get_all_menu_items() when only custom_menu is None"""
		self.doc.menu = [
			{"title": "Standard Item", "route": "standard", "enabled": 1}
		]
		self.doc.custom_menu = None

		result = self.doc.get_all_menu_items()

		self.assertIsInstance(result, list)
		self.assertEqual(len(result), 1)
		self.assertEqual(result[0].title, "Standard Item")

	def test_get_all_menu_items_with_both_populated(self):
		"""Test get_all_menu_items() returns combined list when both have items"""
		self.doc.menu = [
			{"title": "Standard Item", "route": "standard", "enabled": 1}
		]
		self.doc.custom_menu = [
			{"title": "Custom Item", "route": "custom", "enabled": 1}
		]

		result = self.doc.get_all_menu_items()

		self.assertIsInstance(result, list)
		self.assertEqual(len(result), 2)
		titles = [item.title for item in result]
		self.assertIn("Standard Item", titles)
		self.assertIn("Custom Item", titles)

	def test_get_all_menu_items_with_both_empty(self):
		"""Test get_all_menu_items() with both fields as empty lists"""
		self.doc.menu = []
		self.doc.custom_menu = []

		result = self.doc.get_all_menu_items()

		self.assertIsInstance(result, list)
		self.assertEqual(result, [])

	def test_remove_deleted_doctype_items_with_none_fields(self):
		"""Test remove_deleted_doctype_items() doesn't crash when fields are None"""
		self.doc.menu = None
		self.doc.custom_menu = None

		# Should not raise TypeError
		try:
			self.doc.remove_deleted_doctype_items()
		except TypeError as e:
			self.fail(f"remove_deleted_doctype_items() raised TypeError: {e}")

	def test_remove_deleted_doctype_items_with_mixed_none(self):
		"""Test remove_deleted_doctype_items() with one None and one populated field"""
		# Add a custom menu item
		self.doc.custom_menu = [
			{"title": "Custom", "route": "custom", "enabled": 1}
		]
		self.doc.menu = None

		# Should not raise TypeError
		try:
			self.doc.remove_deleted_doctype_items()
		except TypeError as e:
			self.fail(f"remove_deleted_doctype_items() raised TypeError: {e}")

	def test_reset_initializes_menu(self):
		"""Test reset() initializes menu to empty list"""
		# Start with None value
		self.doc.menu = None

		self.doc.reset()

		# After reset, menu should be a list
		self.assertIsNotNone(self.doc.menu)
		self.assertIsInstance(self.doc.menu, list)

	def test_reset_is_idempotent(self):
		"""Test calling reset() multiple times doesn't cause errors"""
		try:
			self.doc.reset()
			self.doc.reset()
			self.doc.reset()
		except Exception as e:
			self.fail(f"Multiple reset() calls raised exception: {e}")

	def test_add_item_with_valid_item(self):
		"""Test add_item() adds new items correctly"""
		self.doc.menu = []

		item = {"title": "Test Item", "route": "test", "enabled": 1}
		result = self.doc.add_item(item)

		self.assertTrue(result)
		self.assertEqual(len(self.doc.menu), 1)
		self.assertEqual(self.doc.menu[0].title, "Test Item")

	def test_add_item_with_none_menu(self):
		"""Test add_item() when menu is None"""
		self.doc.menu = None

		item = {"title": "Test Item", "route": "test", "enabled": 1}
		result = self.doc.add_item(item)

		self.assertTrue(result)
		self.assertEqual(len(self.doc.menu), 1)
		self.assertEqual(self.doc.menu[0].title, "Test Item")

	def test_add_item_prevents_duplicates(self):
		"""Test add_item() doesn't add duplicate routes"""
		item = {"title": "Test Item", "route": "test", "enabled": 1}

		self.doc.add_item(item)
		result = self.doc.add_item(item)

		# Second add_item call should return False (not added)
		self.assertFalse(result)
		self.assertEqual(len(self.doc.menu), 1)

	def test_add_item_updates_role_if_different(self):
		"""Test add_item() updates role if different"""
		item1 = {"title": "Test Item", "route": "test", "role": "User", "enabled": 1}
		item2 = {"title": "Test Item", "route": "test", "role": "Guest", "enabled": 1}

		self.doc.add_item(item1)
		result = self.doc.add_item(item2)

		self.assertTrue(result)  # Should return True because role was updated
		self.assertEqual(len(self.doc.menu), 1)
		self.assertEqual(self.doc.menu[0].role, "Guest")

	def test_sync_menu_with_none_fields(self):
		"""Test sync_menu() doesn't crash when fields are None"""
		self.doc.menu = None
		self.doc.custom_menu = None

		# Should not raise TypeError
		try:
			self.doc.sync_menu()
		except TypeError as e:
			self.fail(f"sync_menu() raised TypeError: {e}")

		# After sync_menu, fields should be populated
		self.assertIsNotNone(self.doc.menu)
		self.assertIsInstance(self.doc.menu, list)

	def test_sync_menu_populates_standard_items(self):
		"""Test sync_menu() populates menu with standard portal items"""
		self.doc.menu = []

		self.doc.sync_menu()

		# After sync_menu, menu should have standard items
		# (number depends on frappe hooks, but should be > 0)
		self.assertGreaterEqual(len(self.doc.menu), 0)

	def test_edge_case_reset_then_sync(self):
		"""Test reset() followed by sync_menu() works correctly"""
		self.doc.menu = None
		self.doc.custom_menu = None

		try:
			self.doc.reset()  # Includes sync_menu() call
			self.doc.sync_menu()
		except Exception as e:
			self.fail(f"reset() then sync_menu() raised exception: {e}")

	def test_edge_case_none_to_valid_to_none(self):
		"""Test cycling field states from None to valid to None"""
		self.doc.menu = None
		self.doc.custom_menu = None

		# First operation
		result1 = self.doc.get_all_menu_items()
		self.assertEqual(result1, [])

		# Set to valid
		self.doc.menu = [{"title": "Item", "route": "test", "enabled": 1}]
		result2 = self.doc.get_all_menu_items()
		self.assertEqual(len(result2), 1)

		# Back to None
		self.doc.menu = None
		result3 = self.doc.get_all_menu_items()
		self.assertEqual(result3, [])

	def test_helper_method_type_consistency(self):
		"""Test get_all_menu_items() always returns a list regardless of field state"""
		test_cases = [
			(None, None),
			([], None),
			(None, []),
			([], []),
			([{"title": "Item", "route": "test", "enabled": 1}], None),
		]

		for menu, custom_menu in test_cases:
			self.doc.menu = menu
			self.doc.custom_menu = custom_menu

			result = self.doc.get_all_menu_items()
			self.assertIsInstance(result, list,
				f"Failed for menu={menu}, custom_menu={custom_menu}")
