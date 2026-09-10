# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


class NavbarSettings(Document):
	_DOCTYPE_NAME = "Navbar Settings"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.navbar_item.navbar_item import NavbarItem
		from frappe.types import DF

		announcement_widget: DF.TextEditor | None
		announcement_widget_color: DF.Color | None
		app_logo: DF.AttachImage | None
		dismissible_announcement_widget: DF.Check
		help_dropdown: DF.Table[NavbarItem]
		settings_dropdown: DF.Table[NavbarItem]
	# end: auto-generated types


def get_app_logo():
	app_logo = frappe.get_website_settings("app_logo") or frappe.get_cached_value(
		"Navbar Settings",
		"Navbar Settings",
		"app_logo",
	)

	if not app_logo:
		logos = frappe.get_hooks("app_logo_url")
		app_logo = logos[0]
		if len(logos) == 2:
			app_logo = logos[1]

	return app_logo


def get_navbar_settings():
	return frappe.get_single("Navbar Settings")


def sync_standard_items():
	"""Syncs standard items from hooks. Called in migrate"""

	sync_table("settings_dropdown", "standard_navbar_items")
	sync_table("help_dropdown", "standard_help_items")


def sync_table(key, hook):
	navbar_settings = NavbarSettings("Navbar Settings")
	existing_items = {d.item_label: d for d in navbar_settings.get(key) if d.get("is_standard") == 1}
	new_standard_items = {}
	fields_to_process = ["action", "hidden", "item_label", "item_type", "route", "icon"]

	# add new items
	count = 0  # maintain count because list may come from seperate apps
	for item in frappe.get_hooks(hook):
		# For existing NavbarItem, delete existing records and update with key-value pair from hooks.
		if item.get("item_label") in existing_items:
			for field in fields_to_process:
				if hasattr(existing_items[item.get("item_label")], field):
					delattr(existing_items[item.get("item_label")], field)

			for k, v in item.items():
				existing_items[item.get("item_label")].update({k: v})

		if item.get("item_label") not in existing_items:
			item.update({"is_standard": 1})
			navbar_settings.append(key, item, count)
		new_standard_items[item.get("item_label")] = True
		count += 1

	# remove unused items
	items = navbar_settings.get(key)
	items = [item for item in items if not (item.is_standard and (item.item_label not in new_standard_items))]
	navbar_settings.set(key, items)

	navbar_settings.save()
