# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class DataImportLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		data_import: DF.Link | None
		docname: DF.Data | None
		exception: DF.Text | None
		log_index: DF.Int
		messages: DF.Code | None
		row_indexes: DF.Code | None
		success: DF.Check
	# end: auto-generated types

	no_feed_on_delete = True

	pass
