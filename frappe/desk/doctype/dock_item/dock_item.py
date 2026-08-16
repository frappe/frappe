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

		hidden: DF.Check
		module: DF.Link | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		workspace: DF.Link | None
	# end: auto-generated types

	pass
