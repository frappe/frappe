# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document


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


def get_app_logo():
	app_logo = frappe.db.get_single_value("Navbar Settings", "app_logo", cache=True)
	if not app_logo:
		app_logo = frappe.get_hooks("app_logo_url")[-1]

	return app_logo


def get_navbar_settings():
	navbar_settings = frappe.get_single("Navbar Settings")
	return navbar_settings
