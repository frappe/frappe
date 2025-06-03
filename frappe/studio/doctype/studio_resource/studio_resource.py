# Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class StudioResource(Document):
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
		resource_name: DF.Data
		resource_type: DF.Literal["Document List", "Document", "API Resource"]
		transform: DF.Code | None
		transform_results: DF.Check
		url: DF.Data | None
		whitelisted_methods: DF.JSON | None
	# end: auto-generated types

	def before_save(self):
		self.validate_config()
		self.set_json_fields()

	def set_json_fields(self):
		if isinstance(self.fields, list):
			self.fields = frappe.as_json(self.fields, indent=None)

		if isinstance(self.filters, list):
			self.filters = frappe.as_json(self.filters, indent=None)

		if isinstance(self.whitelisted_methods, list):
			self.whitelisted_methods = frappe.as_json(self.whitelisted_methods, indent=None)

	def validate_config(self):
		if self.resource_type == "API Resource" and not self.url:
			frappe.throw(_("Please set API URL for Data Source {0}").format(self.name))

		else:
			if self.resource_type in ["Document", "Document List"] and not self.document_type:
				frappe.throw(_("Please set Document Type for Data Source {0}").format(self.name))

			if self.resource_type == "Document List" and not self.fields:
				frappe.throw(_("Please set fields to fetch for Data Source {0}").format(self.name))

			if self.resource_type == "Document":
				if self.fetch_document_using_filters:
					if not self.filters:
						frappe.throw(_("Please set filters to fetch the Data Source {0}").format(self.name))
					self.document_name = ""
				else:
					if not self.document_name:
						frappe.throw(
							_("Please set the document name to fetch the Data Source {0}").format(self.name)
						)
					self.filters = []
