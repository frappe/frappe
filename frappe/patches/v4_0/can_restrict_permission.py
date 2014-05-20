# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	if "can_restrict" not in frappe.db.get_table_columns("DocPerm"):
		frappe.db.sql_ddl("alter table tabDocPerm change `restrict` `can_restrict` int(1) DEFAULT NULL")
