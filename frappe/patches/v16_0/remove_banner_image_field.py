# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe


def execute():
	"""Remove banner_image field from User, Website Settings and Web Form doctypes."""

	# Drop column from User
	if frappe.db.table_exists("User") and "banner_image" in frappe.db.get_table_columns("User"):
		frappe.db.sql("ALTER TABLE `tabUser` DROP COLUMN `banner_image`")

	# Drop column from Web Form
	if frappe.db.table_exists("Web Form") and "banner_image" in frappe.db.get_table_columns("Web Form"):
		frappe.db.sql("ALTER TABLE `tabWeb Form` DROP COLUMN `banner_image`")

	# Remove from Singles (Website Settings)
	frappe.db.sql("DELETE FROM `tabSingles` WHERE doctype = 'Website Settings' AND field = 'banner_image'")

	frappe.reload_doc("core", "doctype", "user", force=True)
	frappe.reload_doc("website", "doctype", "website_settings", force=True)
	frappe.reload_doc("website", "doctype", "web_form", force=True)
