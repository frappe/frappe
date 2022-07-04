# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class CustomRole(Document):
	def validate(self):
		if self.report and not self.ref_doctype:
			self.ref_doctype = frappe.db.get_value("Report", self.report, "ref_doctype")


def get_custom_allowed_roles(field, name):
	allowed_roles = []
	custom_role = frappe.db.get_value("Custom Role", {field: name}, "name")
	if custom_role:
		custom_role_doc = frappe.get_doc("Custom Role", custom_role)
		allowed_roles = [d.role for d in custom_role_doc.roles]

	return allowed_roles
