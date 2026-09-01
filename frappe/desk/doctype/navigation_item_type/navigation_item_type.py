# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

# The writes that are an app's content arriving on a site rather than a person editing it: an
# install, an app update, a migrate, or a fixture import. Each is a real route by which a type
# ships, and without them installing an app that contributes a kind would fail on every site.
SYSTEM_WRITE_FLAGS = ("in_install", "in_patch", "in_migrate", "in_import", "in_setup_wizard")


class NavigationItemType(Document):
	"""A kind of navigation item, contributed by an app as a file.

	Two things make a kind, and neither of them is a row of code. The kind's *declaration* is this
	record, shipped at `<app>/<module>/navigation_item_type/<name>/<name>.json` and re-imported by
	the ordinary migrate sync. What an item of the kind *does* on click is a JS module shipped
	beside it. Server code is optional, and arrives through a hook keyed by type name rather than
	through a dotted path stored here: a path in a database row is code-in-data, and since a type
	row and its handler are always edited in the same commit, storing the path would buy nothing
	and cost a way to change behaviour by editing a record.

	Rows are therefore code-owned. Nobody has create or write permission on this doctype — a
	non-developer minting a row would be minting behaviour — and the guard below stops the two
	remaining routes, developer-mode authoring aside.
	"""

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
		"""Refuse a write that is not an app shipping its own content.

		The permission rows already withhold create and write from every role, so this only has to
		catch what permissions cannot see: a write made with `ignore_permissions`, and Administrator,
		who is exempt from permission checks entirely. `Rail`'s equivalent guard is conditional
		because its three layers share one table and two of them must stay writable at runtime.
		This one is unconditional, because every row here is app content and there is no second
		layer to protect.
		"""
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
		"""Write this type to its file, so authoring it and shipping it are one step.

		The path is the usual per-record folder inside the module — the same walk that imports
		`Sidebar` and `Workspace` — which is what lets the row arrive at migrate and its renderer
		at build on two independent channels, with no manifest to disagree with a seeder.
		"""
		from frappe.modules.export_file import export_to_files

		if frappe.flags.in_import or not frappe.conf.developer_mode:
			return

		export_to_files(record_list=[[self.doctype, self.name]], record_module=self.module)
