# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from frappe.model.document import Document


class DataExport(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		export_without_main_header: DF.Check
		file_type: DF.Literal["Excel", "CSV"]
		reference_doctype: DF.Link
	# end: auto-generated types

	pass
