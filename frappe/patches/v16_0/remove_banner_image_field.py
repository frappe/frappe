# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def execute():
	"""Remove banner_image field from User doctype only (issue #37046)."""

	# Remove any Custom Field for banner_image on User (so form no longer shows the field)
	frappe.db.sql(
		"DELETE FROM `tabCustom Field` WHERE dt = %(dt)s AND fieldname = %(fieldname)s",
		{"dt": "User", "fieldname": "banner_image"},
	)

	# Drop column from User table if it exists (e.g. existing sites before the field was removed from JSON)
	if frappe.db.table_exists("User") and frappe.db.has_column("User", "banner_image"):
		frappe.db.sql_ddl("ALTER TABLE `tabUser` DROP COLUMN `banner_image`")

	frappe.reload_doc("core", "doctype", "user", force=True)
