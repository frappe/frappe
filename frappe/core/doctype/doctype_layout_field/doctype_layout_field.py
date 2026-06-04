# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

# import frappe
from frappe.model.document import Document


class DocTypeLayoutField(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		allow_in_quick_entry: DF.Check
		bold: DF.Check
		default: DF.SmallText | None
		depends_on: DF.Data | None
		description: DF.SmallText | None
		fieldname: DF.Literal[None]
		hidden: DF.Check
		in_list_view: DF.Check
		in_standard_filter: DF.Check
		label: DF.Data | None
		mandatory_depends_on: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		read_only: DF.Check
		read_only_depends_on: DF.Data | None
		reqd: DF.Check
		translatable: DF.Check
	# end: auto-generated types

	pass
