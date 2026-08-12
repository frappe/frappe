# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

"""The v16 sidebar store, kept as an inert archive.

Nothing reads this at runtime and nothing writes a row to it. It stays because it is where a
v16 site's sidebars actually are: the conversion in
`frappe.desk.doctype.module_sidebar.module_sidebar` reads these rows, and keeping them is what
makes that conversion re-runnable -- a site migrated by a bad build can be migrated again from
the same source, and nothing anywhere in the upgrade destroys anything.

Retiring, and deliberately not before the rest: while it is here a site migrated by a bad
build can be migrated again from the same rows. It goes with the icon-grid batch, on one of the
two triggers written down in `frappe/desk/RETIRING.md`.
"""

import frappe
from frappe import _
from frappe.model.document import Document


class WorkspaceSidebar(Document):
	_DOCTYPE_NAME = "Workspace Sidebar"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.workspace_sidebar_item.workspace_sidebar_item import WorkspaceSidebarItem
		from frappe.types import DF

		app: DF.Autocomplete | None
		for_user: DF.Link | None
		header_icon: DF.Icon | None
		items: DF.Table[WorkspaceSidebarItem]
		module: DF.Text | None
		module_onboarding: DF.Link | None
		standard: DF.Check
		title: DF.Data | None
	# end: auto-generated types

	def validate(self):
		self.refuse_new_rows()

	def refuse_new_rows(self):
		"""An archive takes no new entries.

		A row created here would be a sidebar nothing renders, and -- worse -- a source the
		conversion would read on its next run and turn into a layer somebody never authored.
		Editing an existing row is refused for the same reason.

		Deleting is deliberately not refused: an operator clearing out an archive they have
		finished with is doing the one thing to it that is safe.
		"""
		if frappe.flags.in_migrate or frappe.flags.in_patch or frappe.flags.in_install:
			return

		frappe.throw(
			_(
				"{0} is an archive of the previous navigation and can no longer be edited. "
				"Customize the module's sidebar instead."
			).format(frappe.bold(self.name or self._DOCTYPE_NAME)),
			title=_("Not Editable"),
		)
