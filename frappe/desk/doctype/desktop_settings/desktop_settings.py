# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class DesktopSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		icon_style: DF.Literal["Monochrome", "Subtle", "Subtle Reverse", "Subtle Reverse w Opacity"]
		navbar_style: DF.Literal[
			"Awesomebar",
			"macOS Launchpad",
			"Brand Logo",
			"Brand Logo with Search",
			"Timeless Launchpad",
			"Apps with Search",
		]
		show_app_icons_as_folder: DF.Check
	# end: auto-generated types

	pass
