# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class WorkspaceSidebarItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		child: DF.Check
		collapsible: DF.Check
		display_depends_on: DF.Code | None
		filters: DF.Code | None
		indent: DF.Check
		keep_closed: DF.Check
		label: DF.Data | None
		link_to: DF.DynamicLink | None
		link_type: DF.Literal["DocType", "Page", "Report", "Workspace", "Dashboard", "URL"]
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		route_options: DF.Code | None
		show_arrow: DF.Check
		type: DF.Literal["Link", "Section Break", "Spacer", "Sidebar Item Group"]
		url: DF.Data | None
	# end: auto-generated types

	pass
