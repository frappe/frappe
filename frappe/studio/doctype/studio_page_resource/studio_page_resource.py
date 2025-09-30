# Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class StudioPageResource(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		document_name: DF.Data | None
		document_type: DF.Link | None
		fetch_document_using_filters: DF.Check
		fields: DF.JSON | None
		filters: DF.JSON | None
		limit: DF.Int
		method: DF.Literal["GET", "POST", "PUT", "DELETE"]
		params: DF.JSON | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		resource_name: DF.Data
		resource_type: DF.Literal["Document List", "Document", "API Resource"]
		sort_field: DF.Data | None
		sort_order: DF.Literal["asc", "desc"]
		transform: DF.Code | None
		transform_results: DF.Check
		url: DF.Data | None
		whitelisted_methods: DF.JSON | None
	# end: auto-generated types

	pass
