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
		if not self.has_value_changed("desktop_page"):
			return

		# The desktop page is resolved once per boot and bootinfo is cached per user, so
		# switching it has to rebuild every user's boot.
		frappe.clear_cache()

		# Whatever turns the grid on is responsible for there being a grid: both producers
		# are gated on this setting, so without seeding here a System Manager flipping to it
		# lands on an empty screen. Enqueued rather than run inline -- seeding walks every
		# installed app and every public workspace, which is not what a settings save is for.
		# Flipping the other way deletes nothing, which is what makes the move reversible.
		if self.desktop_page == DESKTOP_ICONS:
			frappe.enqueue(seed_desktop_icons, enqueue_after_commit=True)


def seed_desktop_icons():
	"""Fill a freshly switched-on grid: generated rows, then every app's shipped ones.

	Both producers are idempotent -- they skip an icon that already exists -- so repeated
	flips accumulate nothing.
	"""
	from frappe.desk.doctype.desktop_icon.desktop_icon import (
		create_desktop_icons,
		import_desktop_icon_fixtures,
	)

	create_desktop_icons()
	import_desktop_icon_fixtures()

	# Anyone who booted between the save and this job cached an empty grid, and the rows
	# themselves bust nothing useful -- a generated icon is not `standard`, so its own
	# `on_update` only clears the cache of the user the job runs as.
	frappe.clear_cache()


def get_desktop_page() -> str:
	"""Which page /app/desktop renders. Defaults to `Apps` when unset (fresh install)."""
	# Asked on every boot, and by the fixture-import guard during an install's own doctype
	# sync -- so neither the doctype nor the field can be assumed to exist. Reading either
	# blind would take down the install, or session boot on a site that has pulled the code
	# but not migrated yet, rather than just falling back to the default page.
	try:
		has_field = frappe.get_meta(DesktopSettings._DOCTYPE_NAME).has_field("desktop_page")
	except frappe.DoesNotExistError:
		frappe.clear_last_message()
		return APPS

	if not has_field:
		return APPS

	page = frappe.db.get_single_value(DesktopSettings._DOCTYPE_NAME, "desktop_page")
	return page if page in (APPS, DESKTOP_ICONS) else APPS


def is_desktop_icons_page() -> bool:
	"""True when /app/desktop renders the arrangeable Desktop Icon grid."""
	return get_desktop_page() == DESKTOP_ICONS
