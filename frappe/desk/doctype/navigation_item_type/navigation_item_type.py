# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# The routes by which a shipped type reaches a site without a person editing it.
SYSTEM_WRITE_FLAGS = ("in_install", "in_patch", "in_migrate", "in_import", "in_setup_wizard")


class NavigationItemType(Document):
	"""A kind of navigation item, shipped by an app as a file beside its renderer; rows are code-owned."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		icon: DF.Icon | None
		label: DF.Data | None
		module: DF.Link
		permission_rule: DF.Literal[
			"Readable DocType",
			"Module Contents",
			"Derived From Children",
			"Permitted Page",
			"Always Visible",
			"Custom",
		]
		target_doctype: DF.Link | None
		type_name: DF.Data
	# end: auto-generated types

	def validate(self):
		self.validate_app_content()

	def validate_app_content(self):
		"""Refuse writes outside developer mode or a system write; permissions miss Administrator."""
		if frappe.conf.developer_mode:
			return

		if any(frappe.flags.get(flag) for flag in SYSTEM_WRITE_FLAGS):
			return

		frappe.throw(
			_(
				"{0} is contributed by an app and can only be authored in developer mode. "
				"An app adds a navigation kind by shipping this record and its renderer together."
			).format(frappe.bold(self.name)),
			title=_("Not Editable"),
		)

	def on_update(self):
		self.export_type()

	def export_type(self):
		"""Write this type to its module folder, the same walk that imports `Sidebar` and `Workspace`."""
		from frappe.modules.export_file import export_to_files

		if frappe.flags.in_import or not frappe.conf.developer_mode:
			return

		export_to_files(record_list=[[self.doctype, self.name]], record_module=self.module)
