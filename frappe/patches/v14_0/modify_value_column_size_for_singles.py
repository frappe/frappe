import frappe


def execute() -> None:
	if frappe.db.db_type == "mariadb":
		frappe.db.sql_ddl("alter table `tabSingles` modify column `value` longtext")
