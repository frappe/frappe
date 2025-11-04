import frappe


def execute():
	if frappe.db.db_type == "mariadb":
		frappe.db.sql(
			"ALTER TABLE __UserSettings CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
		)
