# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def execute():
	frappe.reload_doc("core", "doctype", "DocField")

	if frappe.db.has_column("DocField", "show_days"):
		frappe.db.sql(
			"""
			UPDATE
				tabDocField
			SET
				hide_days = 1 WHERE show_days = 0
		"""
		)
		frappe.db.sql_ddl("alter table tabDocField drop column show_days")

	if frappe.db.has_column("DocField", "show_seconds"):
		frappe.db.sql(
			"""
			UPDATE
				tabDocField
			SET
				hide_seconds = 1 WHERE show_seconds = 0
		"""
		)
		frappe.db.sql_ddl("alter table tabDocField drop column show_seconds")

	frappe.clear_cache(doctype="DocField")
