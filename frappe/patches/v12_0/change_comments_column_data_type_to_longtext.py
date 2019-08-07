import frappe
from frappe.core.utils import find

def execute():
	if frappe.db.db_type != "postgres":
		doctypes = frappe.get_all("DocType")
		for doctype in doctypes:
			columns = frappe.db.get_table_columns_description("tab{}".format(doctype.name))
			comments_column = find(columns, lambda x: x.name == "_comments")
			if comments_column and comments_column.type != "longtext":
				frappe.db.sql("ALTER TABLE `tab{}` MODIFY _comments LONGTEXT".format(doctype.name))
