import frappe

def execute():
	frappe.db.sql(frappe.qb.change_table_type(tb = "__Auth",col = "password",type = "TEXT"))
