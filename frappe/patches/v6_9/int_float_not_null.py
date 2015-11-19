from __future__ import unicode_literals
import frappe

def execute():
	for doctype in frappe.get_all("DocType", filters={"issingle": 0}):
		doctype = doctype.name

		for column in frappe.db.sql("desc `tab{doctype}`".format(doctype=doctype), as_dict=True):
			fieldname = column["Field"]
			column_type = column["Type"]

			if not (column_type.startswith("int") or column_type.startswith("decimal")):
				continue

			frappe.db.sql("""update `tab{doctype}` set `{fieldname}`=0 where `{fieldname}` is null"""\
				.format(doctype=doctype, fieldname=fieldname))
