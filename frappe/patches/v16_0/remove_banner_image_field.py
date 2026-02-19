# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def execute():
	"""Remove banner_image field from User doctype only (issue #37046)."""

	# Remove any Custom Field for banner_image on User (so form no longer shows the field)
	frappe.db.delete("Custom Field", {"dt": "User", "fieldname": "banner_image"})

	# Drop column from User table
	if frappe.db.table_exists("User") and "banner_image" in frappe.db.get_table_columns("User"):
		frappe.db.sql("ALTER TABLE `tabUser` DROP COLUMN `banner_image`")

	frappe.reload_doc("core", "doctype", "user", force=True)
	frappe.clear_cache(doctype="User")
