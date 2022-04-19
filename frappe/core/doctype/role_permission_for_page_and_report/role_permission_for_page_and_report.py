# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.core.doctype.report.report import is_prepared_report_disabled
from frappe.model.document import Document


class RolePermissionforPageandReport(Document):
	@frappe.whitelist()
	def set_report_page_data(self):
		self.set_custom_roles()
		self.check_prepared_report_disabled()

	def set_custom_roles(self):
		args = self.get_args()
		self.set("roles", [])

		name = frappe.db.get_value("Custom Role", args, "name")
		if name:
			doc = frappe.get_doc("Custom Role", name)
			roles = doc.roles
		else:
			roles = self.get_standard_roles()

		self.set("roles", roles)

	def check_prepared_report_disabled(self):
		if self.report:
			self.disable_prepared_report = is_prepared_report_disabled(self.report)

	def get_standard_roles(self):
		doctype = self.set_role_for
		docname = self.page if self.set_role_for == "Page" else self.report
		doc = frappe.get_doc(doctype, docname)
		return doc.roles

	@frappe.whitelist()
	def reset_roles(self):
		roles = self.get_standard_roles()
		self.set("roles", roles)
		self.update_custom_roles()
		self.update_disable_prepared_report()

	@frappe.whitelist()
	def update_report_page_data(self):
		self.update_custom_roles()
		self.update_disable_prepared_report()

	def update_custom_roles(self):
		args = self.get_args()
		name = frappe.db.get_value("Custom Role", args, "name")

		args.update({"doctype": "Custom Role", "roles": self.get_roles()})

		if self.report:
			args.update({"ref_doctype": frappe.db.get_value("Report", self.report, "ref_doctype")})

		if name:
			custom_role = frappe.get_doc("Custom Role", name)
			custom_role.set("roles", self.get_roles())
			custom_role.save()
		else:
			frappe.get_doc(args).insert()

	def update_disable_prepared_report(self):
		if self.report:
			# intentionally written update query in frappe.db.sql instead of frappe.db.set_value
			frappe.db.sql(
				""" update `tabReport` set disable_prepared_report = %s
				where name = %s""",
				(self.disable_prepared_report, self.report),
			)

	def get_args(self, row=None):
		name = self.page if self.set_role_for == "Page" else self.report
		check_for_field = self.set_role_for.replace(" ", "_").lower()

		return {check_for_field: name}

	def get_roles(self):
		roles = []
		for data in self.roles:
			if data.role != "All":
				roles.append({"role": data.role, "parenttype": "Custom Role"})
		return roles

	def update_status(self):
		return frappe.render_template
