from __future__ import unicode_literals
import frappe

def execute():
	#if frappe.db.exists('DocType', 'View log'):
	if frappe.database.database.Database.table_exists(frappe.db,'View log'):

            # for mac users direct renaming would not work since mysql for mac saves table name in lower case
            # so while renaming `tabView log` to `tabView Log` we get "Table 'tabView Log' already exists" error
            # more info https://stackoverflow.com/a/44753093/5955589 ,
            # https://dev.mysql.com/doc/refman/8.0/en/server-system-variables.html#sysvar_lower_case_table_names

            # here we are creating a temp table to store view log data
            frappe.db.sql("CREATE TABLE `ViewLogTemp` AS SELECT * FROM `tabView log`")

            # deleting old View log table
            frappe.db.sql("DROP table `tabView log`")
            frappe.delete_doc('DocType', 'View log')

	elif frappe.database.database.Database.table_exists(frappe.db,'View Log'): 
		# here we are creating a temp table to store view log data
		frappe.db.sql("CREATE TABLE `ViewLogTemp` AS SELECT * FROM `tabView Log`")


	# deleting old View log table
	frappe.db.sql("DROP table `tabView Log`")
	frappe.delete_doc('DocType', 'View Log')

	# reloading view log doctype to create `tabView Log` table
	frappe.reload_doc('core', 'doctype', 'view_log')

	# Move the data to newly created `tabView Log` table
	frappe.db.sql("INSERT INTO `tabView Log` SELECT * FROM `ViewLogTemp`")
	frappe.db.commit()

	# Delete temporary table
	frappe.db.sql("DROP table `ViewLogTemp`")
