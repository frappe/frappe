# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class DocTypeLayoutChildTable(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		child_layout: DF.Link
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		table_fieldname: DF.Data
	# end: auto-generated types

	pass
