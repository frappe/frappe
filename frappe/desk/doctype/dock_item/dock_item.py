# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class DockItem(Document):
	_DOCTYPE_NAME = "Dock Item"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		added: DF.Check
		hidden: DF.Check
		icon: DF.Icon | None
		link_to: DF.DynamicLink | None
		link_type: DF.Literal["", "Workspace", "URL"]
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		sidebar: DF.Link | None
		title: DF.Data | None
		url: DF.Data | None
	# end: auto-generated types

	pass
