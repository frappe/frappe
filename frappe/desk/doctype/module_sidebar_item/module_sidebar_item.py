# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ModuleSidebarItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		label: DF.Data | None
		link_to: DF.DynamicLink | None
		link_type: DF.Literal["", "DocType", "Page", "Report", "Dashboard", "URL"]
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		type: DF.Literal["Link", "Section Break", "Spacer"]
		url: DF.Data | None
	# end: auto-generated types

	pass
