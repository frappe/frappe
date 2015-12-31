# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import frappe.permissions

def execute():
	frappe.reload_doc("core", "doctype", "docperm")
	table_columns = frappe.db.get_table_columns("DocPerm")

	if "restricted" in table_columns:
		frappe.db.sql("""update `tabDocPerm` set apply_user_permissions=1 where apply_user_permissions=0
			and restricted=1""")

	if "match" in table_columns:
		frappe.db.sql("""update `tabDocPerm` set apply_user_permissions=1
			where apply_user_permissions=0 and ifnull(`match`, '')!=''""")

	# change Restriction to User Permission in tabDefaultValue
	frappe.db.sql("""update `tabDefaultValue` set parenttype='User Permission' where parenttype='Restriction'""")

	frappe.clear_cache()

