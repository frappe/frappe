# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class NavbarSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.navbar_item.navbar_item import NavbarItem
		from frappe.types import DF

		app_logo: DF.AttachImage | None
		help_dropdown: DF.Table[NavbarItem]
		logo_width: DF.Int
		settings_dropdown: DF.Table[NavbarItem]
	# end: auto-generated types

	@frappe.whitelist()
	def set_items(self):
		standard_navbar_items = [
			{
				"item_label": "My Profile",
				"item_type": "Route",
				"route": "/app/user-profile",
				"is_standard": 1,
			},
			{
				"item_label": "My Settings",
				"item_type": "Action",
				"action": "frappe.ui.toolbar.route_to_user()",
				"is_standard": 1,
			},
			{
				"item_label": "View Website",
				"item_type": "Action",
				"action": "frappe.ui.toolbar.view_website()",
				"is_standard": 1,
			},
			{
				"item_label": "App Launcher",
				"item_type": "Route",
				"route": "/apps",
				"is_standard": 1,
			},
			{
				"item_type": "Separator",
				"is_standard": 1,
				"item_label": "",
			},
			{
				"item_label": "Reload",
				"item_type": "Action",
				"action": "frappe.ui.toolbar.clear_cache()",
				"is_standard": 1,
			},
			{
				"item_label": "Session Defaults",
				"item_type": "Action",
				"action": "frappe.ui.toolbar.setup_session_defaults()",
				"is_standard": 1,
			},
			{
				"item_label": "Toggle Full Width",
				"item_type": "Action",
				"action": "frappe.ui.toolbar.toggle_full_width()",
				"is_standard": 1,
			},
			{
				"item_label": "Toggle Theme",
				"item_type": "Action",
				"action": "new frappe.ui.ThemeSwitcher().show()",
				"is_standard": 1,
			},
			{
				"item_type": "Separator",
				"is_standard": 1,
				"item_label": "",
			},
			{
				"item_label": "Log out",
				"item_type": "Action",
				"action": "frappe.app.logout()",
				"is_standard": 1,
			},
		]

		standard_help_items = [
			{
				"item_label": "About",
				"item_type": "Action",
				"action": "frappe.ui.toolbar.show_about()",
				"is_standard": 1,
			},
			{
				"item_label": "Keyboard Shortcuts",
				"item_type": "Action",
				"action": "frappe.ui.toolbar.show_shortcuts(event)",
				"is_standard": 1,
			},
			{
				"item_label": "Frappe Support",
				"item_type": "Route",
				"route": "https://frappe.io/support",
				"is_standard": 1,
			},
		]

		self.settings_dropdown = []
		self.help_dropdown = []

		for item in standard_navbar_items:
			self.append("settings_dropdown", item)

		for item in standard_help_items:
			self.append("help_dropdown", item)

		self.save()


def get_app_logo():
	app_logo = frappe.db.get_single_value("Navbar Settings", "app_logo", cache=True)
	if not app_logo:
		app_logo = frappe.get_hooks("app_logo_url")[-1]

	return app_logo


def get_navbar_settings():
	return frappe.get_single("Navbar Settings")
