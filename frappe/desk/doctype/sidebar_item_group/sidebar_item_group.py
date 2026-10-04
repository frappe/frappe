# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.desk.desk_views import DeskViews
from frappe.model.document import Document


class SidebarItemGroup(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.sidebar_item_group_link.sidebar_item_group_link import SidebarItemGroupLink
		from frappe.types import DF

		app: DF.Autocomplete | None
		links: DF.Table[SidebarItemGroupLink]
		sidebar: DF.Link | None
	# end: auto-generated types


@frappe.whitelist()
def get_reports(module_name: str | None = None):
	reports_info = []
	if module_name:
		sidebar_group = frappe.get_doc("Sidebar Item Group", module_name)
		for report_links in sidebar_group.links:
			allowed_reports = DeskViews.get_allowed_reports()
			if report_links.report in allowed_reports:
				reports_info.append(allowed_reports[report_links.report])
		return reports_info
