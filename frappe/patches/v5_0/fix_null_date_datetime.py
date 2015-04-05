from __future__ import unicode_literals
import frappe

def execute():
	for table in frappe.db.get_tables():
		changed = False
		desc = frappe.db.sql("desc `{table}`".format(table=table), as_dict=True)
		for field in desc:
			if field["Type"] == "date":
				frappe.db.sql("""update `{table}` set `{fieldname}`=null where `{fieldname}`='0000-00-00'""".format(
					table=table, fieldname=field["Field"]))
				changed = True

			elif field["Type"] == "datetime(6)":
				frappe.db.sql("""update `{table}` set `{fieldname}`=null where `{fieldname}`='0000-00-00 00:00:00.000000'""".format(
					table=table, fieldname=field["Field"]))
				changed = True

		if changed:
			frappe.db.commit()
