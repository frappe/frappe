from __future__ import unicode_literals
import frappe

def execute():
	for table in frappe.db.sql_list("show tables"):
		for field in frappe.db.sql("desc `%s`" % table):
			if field[1]=="datetime":
				frappe.db.sql("alter table `%s` change `%s` `%s` datetime(6)" % \
					 (table, field[0], field[0]))
			elif field[1]=="time":
				frappe.db.sql("alter table `%s` change `%s` `%s` time(6)" % \
					 (table, field[0], field[0]))
