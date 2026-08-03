# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class ModuleSidebarItem(Document):
	_DOCTYPE_NAME = "Module Sidebar Item"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		child: DF.Check
		collapsible: DF.Check
		default_workspace: DF.Check
		filters: DF.Code | None
		icon: DF.Icon | None
		indent: DF.Check
		keep_closed: DF.Check
		key: DF.Data | None
		label: DF.Data | None
		link_to: DF.DynamicLink | None
		link_type: DF.Literal["DocType", "Page", "Report", "Workspace", "Dashboard", "URL"]
		navigate_to_tab: DF.Autocomplete | None
		open_in_new_tab: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		route_options: DF.Code | None
		show_arrow: DF.Check
		source_workspace: DF.Data | None
		type: DF.Literal["Link", "Section Break"]
		url: DF.Data | None
	# end: auto-generated types

	pass
