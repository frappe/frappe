# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class DockOrder(Document):
	_DOCTYPE_NAME = "Dock Order"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.dock_module.dock_module import DockModule
		from frappe.types import DF

		modules: DF.Table[DockModule]
	# end: auto-generated types

	def on_update(self):
		"""The site's dock is in everybody's boot, so everybody's boot is stale.

		The whole key, not one user's: unlike a sidebar customization -- which is either the
		site's or one person's -- this document has no per-user variant to be surgical about.
		"""
		frappe.cache.delete_key("bootinfo")
