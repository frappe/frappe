# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	for dt in frappe.db.sql_list("""select name from `tabDocType` where issingle=0"""):
		desc = dict((d["Field"], d) for d in frappe.db.sql("desc `tab{}`".format(dt), as_dict=True))
		alter_table = []

		if desc["name"]["Type"] != "varchar(255)":
			alter_table.append("change `name` `name` varchar(255) not null")

		for fieldname in ("modified_by", "owner", "parent", "parentfield", "parenttype"):
			if desc[fieldname]["Type"] != "varchar(255)":
				alter_table.append("change `{fieldname}` `{fieldname}` varchar(255)".format(fieldname=fieldname))

		if alter_table:
			alter_table_query = "alter table `tab{doctype}` {alter_table}".format(doctype=dt, alter_table=",\n".join(alter_table))
			# print alter_table_query
			frappe.db.sql_ddl(alter_table_query)

