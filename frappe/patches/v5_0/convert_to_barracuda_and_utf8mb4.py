from __future__ import unicode_literals
import frappe
import sys

def execute():
	check_if_ready_for_barracuda()

	for table in frappe.db.get_tables():
		frappe.db.sql_ddl("""alter table `{0}` ENGINE=InnoDB ROW_FORMAT=COMPRESSED""".format(table))
		frappe.db.sql_ddl("""alter table `{0}` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci""".format(table))

def check_if_ready_for_barracuda():
	mariadb_variables = frappe._dict(frappe.db.sql("""show variables"""))
	for key, value in {
			"innodb_file_format": "Barracuda",
			"innodb_file_per_table": "ON",
			"innodb_large_prefix": "ON",
			"character_set_server": "utf8mb4",
			"collation_server": "utf8mb4_unicode_ci"
		}.items():

		if mariadb_variables.get(key) != value:
			print "="*80
			print "Please add this to MariaDB's my.cnf and restart MariaDB before proceeding"
			print
			print expected
			print "="*80
			sys.exit(1)
			# raise Exception, "MariaDB needs to be configured!"

expected = """[mysqld]
innodb-file-format=barracuda
innodb-file-per-table=1
innodb-large-prefix=1
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

[mysql]
default-character-set = utf8mb4
"""
