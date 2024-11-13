# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class CustomRole(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.has_role.has_role import HasRole
		from frappe.types import DF

		page: DF.Link | None
		ref_doctype: DF.Data | None
		report: DF.Link | None
		roles: DF.Table[HasRole]
	# end: auto-generated types

	def validate(self):
		if self.report and not self.ref_doctype:
			self.ref_doctype = frappe.db.get_value("Report", self.report, "ref_doctype")

	def get_permission_log_options(self, event=None):
		if self.report:
			return {"for_doctype": "Report", "for_document": self.report, "fields": ["roles"]}
		return {"for_doctype": "Page", "for_document": self.page, "fields": ["roles"]}


def get_custom_allowed_roles(field, name):
	allowed_roles = []
	custom_role = frappe.db.get_value("Custom Role", {field: name}, "name")
	if custom_role:
		custom_role_doc = frappe.get_doc("Custom Role", custom_role)
		allowed_roles = [d.role for d in custom_role_doc.roles]

	return allowed_roles
