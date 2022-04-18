# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document

STANDARD_NAVBAR_ITEMS = [
	{
		"item_label": "My Profile",
		"item_type": "Route",
		"route": "/app/user-profile",
		"is_standard": 1,
		"id": "my_profile",
	},
	{
		"item_label": "My Settings",
		"item_type": "Action",
		"action": "frappe.ui.toolbar.route_to_user()",
		"is_standard": 1,
		"id": "my_settings",
	},
	{
		"item_label": "Session Defaults",
		"item_type": "Action",
		"action": "frappe.ui.toolbar.setup_session_defaults()",
		"is_standard": 1,
		"id": "session_defauls",
	},
	{
		"item_label": "Reload",
		"item_type": "Action",
		"action": "frappe.ui.toolbar.clear_cache()",
		"is_standard": 1,
		"id": "reload",
	},
	{
		"item_label": "View Website",
		"item_type": "Action",
		"action": "frappe.ui.toolbar.view_website()",
		"is_standard": 1,
		"id": "view_website",
	},
	{
		"item_label": "Toggle Full Width",
		"item_type": "Action",
		"action": "frappe.ui.toolbar.toggle_full_width()",
		"is_standard": 1,
		"id": "toggle_full_width",
	},
	{
		"item_label": "Toggle Theme",
		"item_type": "Action",
		"action": "new frappe.ui.ThemeSwitcher().show()",
		"is_standard": 1,
		"id": "toggle_theme",
	},
	{
		"item_label": "Background Jobs",
		"item_type": "Route",
		"route": "/app/background_jobs",
		"is_standard": 1,
		"id": "background_jobs",
	},
	{
		"item_type": "Separator",
		"is_standard": 1,
		"id": "logout_separator",
	},
	{
		"item_label": "Log out",
		"item_type": "Action",
		"action": "frappe.app.logout()",
		"is_standard": 1,
		"id": "log_out",
	},
]

STANDARD_HELP_ITEMS = [
	{
		"item_label": "About",
		"item_type": "Action",
		"action": "frappe.ui.toolbar.show_about()",
		"is_standard": 1,
		"id": "about",
	},
	{
		"item_label": "Keyboard Shortcuts",
		"item_type": "Action",
		"action": "frappe.ui.toolbar.show_shortcuts(event)",
		"is_standard": 1,
		"id": "keyboard_shortcut",
	},
	{
		"item_label": "Frappe Support",
		"item_type": "Route",
		"route": "https://frappe.io/support",
		"is_standard": 1,
		"id": "frappe_support",
	},
]


class NavbarSettings(Document):
	def validate(self):
		self.validate_standard_navbar_items()

	def validate_standard_navbar_items(self):
		doc_before_save = self.get_doc_before_save()

		if not doc_before_save:
			return

		before_save_items = [
			item
			for item in doc_before_save.help_dropdown + doc_before_save.settings_dropdown
			if item.is_standard
		]

		after_save_items = [
			item for item in self.help_dropdown + self.settings_dropdown if item.is_standard
		]

		if not frappe.flags.in_patch and (len(before_save_items) > len(after_save_items)):
			frappe.throw(_("Please hide the standard navbar items instead of deleting them"))

	def update_standard_navbar_items(self):
		self._merge_custom_items("settings_dropdown", STANDARD_NAVBAR_ITEMS)
		self._merge_custom_items("help_dropdown", STANDARD_HELP_ITEMS)

	def _merge_custom_items(self, table_name, new_items):
		"""Add/Update standard fields in navbar"""

		existing_items = self.get(table_name)

		def find_existing_field(new_item):
			if not (id := new_item.get("id")) and not frappe.flags.in_patch:
				frappe.throw(_("Standard navbar items should have unique ID."))
			for entry in existing_items:
				if entry.get("id") == id:
					return entry

		for new_item in new_items:
			existing_item = find_existing_field(new_item)

			if not existing_item:
				self.append(table_name, new_item)
			else:
				new_item.pop("item_label", None)  # keep old label
				existing_item.update(new_item)

		for idx, item in enumerate(existing_items, start=1):
			item.idx = idx


def get_app_logo():
	app_logo = frappe.db.get_single_value("Navbar Settings", "app_logo", cache=True)
	if not app_logo:
		app_logo = frappe.get_hooks("app_logo_url")[-1]

	return app_logo


def get_navbar_settings():
	navbar_settings = frappe.get_single("Navbar Settings")
	return navbar_settings
