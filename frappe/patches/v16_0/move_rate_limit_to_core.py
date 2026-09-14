import frappe


def execute():
	if frappe.db.exists("DocType", "Rate Limit"):
		frappe.db.set_value("DocType", "Rate Limit", "module", "Core")

	frappe.reload_doc("core", "doctype", "rate_limit")

	if frappe.db.table_exists("Rate Limit") and frappe.db.has_column("Rate Limit", "user_based"):
		frappe.db.sql("""
            UPDATE `tabRate Limit`
            SET user_based = 0
            WHERE user_based IS NULL
        """)
