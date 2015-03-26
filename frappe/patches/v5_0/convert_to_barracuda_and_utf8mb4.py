from __future__ import unicode_literals
import frappe
from frappe.installer import check_if_ready_for_barracuda

def execute():
	check_if_ready_for_barracuda()

	for table in frappe.db.get_tables():
		frappe.db.sql_ddl("""alter table `{0}` ENGINE=InnoDB ROW_FORMAT=COMPRESSED""".format(table))
		frappe.db.sql_ddl("""alter table `{0}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci""".format(table))

