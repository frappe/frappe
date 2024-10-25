# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def execute() -> None:
	if not frappe.db.table_exists("Data Import"):
		return

	meta = frappe.get_meta("Data Import")
	# if Data Import is the new one, return early
	if meta.fields[1].fieldname == "import_type":
		return

	frappe.db.sql("DROP TABLE IF EXISTS `tabData Import Legacy`")
	frappe.rename_doc("DocType", "Data Import", "Data Import Legacy")
	frappe.db.commit()
	frappe.db.sql("DROP TABLE IF EXISTS `tabData Import`")
	frappe.rename_doc("DocType", "Data Import Beta", "Data Import")
