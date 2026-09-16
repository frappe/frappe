import frappe


# Flow Agent Memory lost its keywords field.
def execute():
	frappe.db.sql_ddl("alter table `tabFlow Agent Memory` drop column if exists `keywords`")
