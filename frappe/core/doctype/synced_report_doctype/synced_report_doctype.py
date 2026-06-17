# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class SyncedReportDoctype(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.synced_report_doctype_table.synced_report_doctype_table import (
			SyncedReportDoctypeTable,
		)
		from frappe.types import DF

		doctype_to_sync: DF.Table[SyncedReportDoctypeTable]
	# end: auto-generated types

	_DOCTYPE_NAME = "Synced Report Doctype"
