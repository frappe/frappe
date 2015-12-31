from __future__ import unicode_literals
import frappe
from frappe.utils import cint, flt

def execute():
	for doctype in frappe.get_all("DocType", filters={"issingle": 0}):
		doctype = doctype.name
		meta = frappe.get_meta(doctype)

		for column in frappe.db.sql("desc `tab{doctype}`".format(doctype=doctype), as_dict=True):
			fieldname = column["Field"]
			column_type = column["Type"]

			if not (column_type.startswith("int") or column_type.startswith("decimal")):
				continue

			frappe.db.sql("""update `tab{doctype}` set `{fieldname}`=0 where `{fieldname}` is null"""\
				.format(doctype=doctype, fieldname=fieldname))

			# alter table
			if column["Null"]=='YES':
				if not meta.get_field(fieldname):
					continue

				default = cint(column["Default"]) if column_type.startswith("int") else flt(column["Default"])
				frappe.db.sql_ddl("""alter table `tab{doctype}`
					change `{fieldname}` `{fieldname}` {column_type} not null default '{default}'""".format(
						doctype=doctype, fieldname=fieldname, column_type=column_type, default=default))


