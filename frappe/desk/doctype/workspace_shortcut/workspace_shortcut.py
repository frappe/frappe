# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

# import frappe
from frappe.model.document import Document


class WorkspaceShortcut(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		color: DF.Color | None
		doc_view: DF.Literal[
			"", "List", "Report Builder", "Dashboard", "Tree", "New", "Calendar", "Kanban", "Image"
		]
		format: DF.Data | None
		icon: DF.Data | None
		kanban_board: DF.Link | None
		label: DF.Data
		link_to: DF.DynamicLink | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		report_ref_doctype: DF.Link | None
		restrict_to_domain: DF.Link | None
		stats_filter: DF.Code | None
		type: DF.Literal["DocType", "Report", "Page", "Dashboard", "URL"]
		url: DF.Data | None
	# end: auto-generated types

	pass
