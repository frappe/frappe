# Copyright (c) 2020, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.tests import IntegrationTestCase


class TestPortalSettings(IntegrationTestCase):
	"""Portal Settings tolerates menu tables that are None instead of empty lists.

	Older sites can end up with `menu` / `custom_menu` unset, which used to raise a
	TypeError while syncing the menu. The None state is reproduced here by assigning
	the attribute directly: `set()` always coerces a falsy value to `[]`, so it cannot
	build the broken document these tests need.
	"""

	def setUp(self):
		super().setUp()
		self.doc = frappe.get_single("Portal Settings")
		# start from a known baseline; the stored menu depends on which apps are installed
		self.doc.set("menu", [])
		self.doc.set("custom_menu", [])

	def tearDown(self):
		# sync_menu() saves when hooks add items; drop that so the site is left untouched
		frappe.db.rollback()
		super().tearDown()

	def test_get_all_menu_items_with_both_none(self):
		self.doc.menu = None
		self.doc.custom_menu = None

		self.assertEqual(self.doc.get_all_menu_items(), [])

	def test_get_all_menu_items_with_menu_none(self):
		self.doc.menu = None
		self.doc.set("custom_menu", [{"title": "Custom Item", "route": "/custom"}])

		items = self.doc.get_all_menu_items()

		self.assertEqual([d.title for d in items], ["Custom Item"])

	def test_get_all_menu_items_with_custom_menu_none(self):
		self.doc.set("menu", [{"title": "Standard Item", "route": "/standard"}])
		self.doc.custom_menu = None

		items = self.doc.get_all_menu_items()

		self.assertEqual([d.title for d in items], ["Standard Item"])

	def test_get_all_menu_items_with_both_populated(self):
		self.doc.set("menu", [{"title": "Standard Item", "route": "/standard"}])
		self.doc.set("custom_menu", [{"title": "Custom Item", "route": "/custom"}])

		items = self.doc.get_all_menu_items()

		self.assertEqual([d.title for d in items], ["Standard Item", "Custom Item"])

	def test_get_all_menu_items_with_both_empty(self):
		self.assertEqual(self.doc.get_all_menu_items(), [])

	def test_get_all_menu_items_always_returns_list(self):
		for menu, custom_menu in (
			(None, None),
			([], None),
			(None, []),
			([], []),
		):
			with self.subTest(menu=menu, custom_menu=custom_menu):
				self.doc.menu = menu
				self.doc.custom_menu = custom_menu

				self.assertEqual(self.doc.get_all_menu_items(), [])

	def test_remove_deleted_doctype_items_with_none_fields(self):
		self.doc.menu = None
		self.doc.custom_menu = None

		self.doc.remove_deleted_doctype_items()

		self.assertEqual(self.doc.get_all_menu_items(), [])

	def test_remove_deleted_doctype_items_with_mixed_none(self):
		self.doc.menu = None
		self.doc.set(
			"custom_menu",
			[
				{"title": "Kept", "route": "/kept", "reference_doctype": "ToDo"},
				{"title": "Dropped", "route": "/dropped", "reference_doctype": "Deleted DocType"},
			],
		)

		self.doc.remove_deleted_doctype_items()

		self.assertEqual([d.title for d in self.doc.custom_menu], ["Kept"])

	def test_sync_menu_with_none_fields(self):
		self.doc.menu = None
		self.doc.custom_menu = None

		self.doc.sync_menu()

		self.assertIsInstance(self.doc.menu, list)
		self.assertIsInstance(self.doc.custom_menu, list)

	def test_sync_menu_only_keeps_existing_doctypes(self):
		self.doc.sync_menu()

		existing_doctypes = set(frappe.get_list("DocType", pluck="name"))
		for item in self.doc.get_all_menu_items():
			self.assertIn(item.reference_doctype, existing_doctypes)

	def test_add_item_appends_new_item(self):
		self.assertTrue(self.doc.add_item({"title": "Test Item", "route": "/test"}))

		self.assertEqual([d.title for d in self.doc.menu], ["Test Item"])
		self.assertTrue(self.doc.menu[0].enabled)

	def test_add_item_with_none_menu(self):
		self.doc.menu = None

		self.assertTrue(self.doc.add_item({"title": "Test Item", "route": "/test"}))

		self.assertEqual([d.title for d in self.doc.menu], ["Test Item"])

	def test_add_item_ignores_duplicate_route(self):
		item = {"title": "Test Item", "route": "/test"}
		self.doc.add_item(item)

		self.assertFalse(self.doc.add_item(item))
		self.assertEqual(len(self.doc.menu), 1)

	def test_add_item_updates_role_if_different(self):
		self.doc.add_item({"title": "Test Item", "route": "/test", "role": "System Manager"})

		self.assertTrue(self.doc.add_item({"title": "Test Item", "route": "/test", "role": "Guest"}))

		self.assertEqual(len(self.doc.menu), 1)
		self.assertEqual(self.doc.menu[0].role, "Guest")

	def test_reset_initializes_menu(self):
		self.doc.menu = None

		self.doc.reset()

		self.assertIsInstance(self.doc.menu, list)

	def test_reset_is_idempotent(self):
		self.doc.reset()
		routes = [d.route for d in self.doc.menu]

		self.doc.reset()

		self.assertEqual([d.route for d in self.doc.menu], routes)
