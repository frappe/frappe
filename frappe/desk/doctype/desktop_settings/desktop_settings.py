# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

# The two things the /app/desktop page can be. These strings are the options of the
# `desktop_page` field, so they are what a system manager sees. This module is the only
# place either is compared -- everything else asks `is_desktop_icons_page()`.
APPS = "Apps"
DESKTOP_ICONS = "Desktop Icons"


class DesktopSettings(Document):
	_DOCTYPE_NAME = "Desktop Settings"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		desktop_page: DF.Literal["Apps", "Desktop Icons"]
		icon_style: DF.Literal["Subtle", "Solid"]
	# end: auto-generated types

	def on_update(self):
		# The desktop page is resolved once per boot and bootinfo is cached per user, so
		# switching it has to rebuild every user's boot.
		if self.has_value_changed("desktop_page"):
			frappe.clear_cache()


def get_desktop_page() -> str:
	"""Which page /app/desktop renders. Defaults to `Apps` when unset (fresh install)."""
	page = frappe.db.get_single_value("Desktop Settings", "desktop_page")
	return page if page in (APPS, DESKTOP_ICONS) else APPS


def is_desktop_icons_page() -> bool:
	"""True when /app/desktop renders the arrangeable Desktop Icon grid."""
	return get_desktop_page() == DESKTOP_ICONS
