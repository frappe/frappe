# Copyright (c) 2018, Frappe Technologies and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class ListFilter(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		filter_name: DF.Data | None
		filters: DF.LongText | None
		for_user: DF.Link | None
		reference_doctype: DF.Link | None
	# end: auto-generated types

	pass
