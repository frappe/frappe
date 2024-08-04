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

		announcement_widget: DF.TextEditor | None
		app_logo: DF.AttachImage | None
		help_dropdown: DF.Table[NavbarItem]
		settings_dropdown: DF.Table[NavbarItem]
	# end: auto-generated types

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

		after_save_items = [item for item in self.help_dropdown + self.settings_dropdown if item.is_standard]

		if not frappe.flags.in_patch and (len(before_save_items) > len(after_save_items)):
			frappe.throw(_("Please hide the standard navbar items instead of deleting them"))


def get_app_logo():
	app_logo = frappe.db.get_single_value("Navbar Settings", "app_logo", cache=True)
	if not app_logo:
		app_logo = frappe.get_hooks("app_logo_url")[-1]

	return app_logo


def get_navbar_settings():
	return frappe.get_single("Navbar Settings")


def sync_standard_items():
	"""Syncs standard items from hooks. Called in migrate"""

	sync_table("settings_dropdown", "standard_navbar_items")
	sync_table("help_dropdown", "standard_help_items")


def sync_table(key, hook):
	navbar_settings = NavbarSettings("Navbar Settings")
	existing_items = {d.item_label: d for d in navbar_settings.get(key)}
	new_items = {}

	# add new items
	count = 0  # matain count because list may come from seperate apps
	for item in frappe.get_hooks(hook):
		if item.get("item_label") not in existing_items:
			navbar_settings.append(key, item, count)
		new_items[item.get("item_label")] = True
		count += 1

	# remove unused items
	def fn(item):
		if item.is_standard and (item.item_label not in new_items):
			return False
		else:
			return True

	navbar_settings.set(key, filter(lambda item: fn, navbar_settings.get(key)))
	navbar_settings.save()
