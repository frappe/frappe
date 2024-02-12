# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class DocumentFollow(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		ref_docname: DF.DynamicLink
		ref_doctype: DF.Link
		user: DF.Link
	# end: auto-generated types

	pass
