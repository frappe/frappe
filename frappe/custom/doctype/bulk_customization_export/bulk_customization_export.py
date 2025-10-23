
# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.modules.utils import export_customizations


class BulkCustomizationExport(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.custom.doctype.bulk_customization_export_doctype.bulk_customization_export_doctype import (
			BulkCustomizationExportDoctype,
		)
		from frappe.types import DF

		doctype_to_export: DF.Table[BulkCustomizationExportDoctype]
		module_to_export: DF.Link
	# end: auto-generated types
	pass


@frappe.whitelist()
def bulk_export_customizations(doc):
	doc = frappe.parse_json(doc)
	module = doc.get("module_to_export")
	if module:
		for row in doc.doctype_to_export:
			export_customizations(
				module=module,
				doctype=row.get("export_doctype"),
				sync_on_migrate=row.get("sync_on_migrate"),
				with_permissions=row.get("export_custom_permissions"),
			)
