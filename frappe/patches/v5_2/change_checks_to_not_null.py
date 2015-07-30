from __future__ import unicode_literals
import frappe
from frappe.utils import cint
from frappe.model import default_fields

def execute():
	for table in frappe.db.get_tables():
		doctype = table[3:]
		if frappe.db.exists("DocType", doctype):
			fieldnames = [df["fieldname"] for df in
				frappe.get_all("DocField", fields=["fieldname"], filters={"parent": doctype})]
			custom_fieldnames = [df["fieldname"] for df in
				frappe.get_all("Custom Field", fields=["fieldname"], filters={"dt": doctype})]

		else:
			fieldnames = custom_fieldnames = []

		for column in frappe.db.sql("""desc `{0}`""".format(table), as_dict=True):
			if column["Type"]=="int(1)":
				fieldname = column["Field"]

				# only change for defined fields, ignore old fields that don't exist in meta
				if not (fieldname in default_fields or fieldname in fieldnames or fieldname in custom_fieldnames):
					continue

				# set 0
				frappe.db.sql("""update `{table}` set `{column}`=0 where `{column}` is null"""\
					.format(table=table, column=fieldname))
				frappe.db.commit()

				# change definition
				frappe.db.sql_ddl("""alter table `{table}`
					modify `{column}` int(1) not null default {default}"""\
					.format(table=table, column=fieldname, default=cint(column["Default"])))
