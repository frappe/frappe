from __future__ import unicode_literals
import frappe
from frappe.database.mariadb.setup_db import check_database_settings
from frappe.model.meta import trim_tables

def execute():
	check_database_settings()

	for table in frappe.db.get_tables():
		frappe.db.sql_ddl("""alter table `{0}` ENGINE=InnoDB ROW_FORMAT=COMPRESSED""".format(table))
		try:
			frappe.db.sql_ddl("""alter table `{0}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci""".format(table))
		except:
			# if row size gets too large, let it be old charset!
			pass

