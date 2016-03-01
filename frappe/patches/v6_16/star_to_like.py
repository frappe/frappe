from __future__ import unicode_literals
import frappe
from frappe.model.db_schema import add_column

def execute():
	frappe.db.sql("""update `tabSingles` set field='_liked_by' where field='_starred_by'""")
	frappe.db.commit()

	for table in frappe.db.get_tables():
		columns = [r[0] for r in frappe.db.sql("DESC `{0}`".format(table))]
		if "_starred_by" in columns and '_liked_by' not in columns:
			frappe.db.sql_ddl("""alter table `{0}` change `_starred_by` `_liked_by` Text """.format(table))

	if not frappe.db.has_column("Communication", "_liked_by"):
		add_column("Communication", "_liked_by", "Text")
