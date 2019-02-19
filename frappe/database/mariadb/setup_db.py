from __future__ import unicode_literals

import frappe
import os, sys
from frappe.database.db_manager import DbManager

def setup_database(force, source_sql, verbose):
	frappe.local.session = frappe._dict({'user':'Administrator'})

	db_name = frappe.local.conf.db_name
	root_conn = get_root_connection(frappe.flags.root_login, frappe.flags.root_password)
	dbman = DbManager(root_conn)
	if force or (db_name not in dbman.get_database_list()):
		dbman.delete_user(db_name)
		dbman.drop_database(db_name)
	else:
		raise Exception("Database %s already exists" % (db_name,))

	dbman.create_user(db_name, frappe.conf.db_password)
	if verbose: print("Created user %s" % db_name)

	dbman.create_database(db_name)
	if verbose: print("Created database %s" % db_name)

	dbman.grant_all_privileges(db_name, db_name)
	dbman.flush_privileges()
	if verbose: print("Granted privileges to user %s and database %s" % (db_name, db_name))

	# close root connection
	root_conn.close()

	bootstrap_database(db_name, verbose, source_sql)

def setup_help_database(help_db_name):
	dbman = DbManager(get_root_connection(frappe.flags.root_login, frappe.flags.root_password))
	dbman.drop_database(help_db_name)

	# make database
	if not help_db_name in dbman.get_database_list():
		try:
			dbman.create_user(help_db_name, help_db_name)
		except Exception as e:
			# user already exists
			if e.args[0] != 1396: raise
		dbman.create_database(help_db_name)
		dbman.grant_all_privileges(help_db_name, help_db_name)
		dbman.flush_privileges()

def drop_user_and_database(db_name, root_login, root_password):
	frappe.local.db = get_root_connection(root_login, root_password)
	dbman = DbManager(frappe.local.db)
	dbman.delete_user(db_name)
	dbman.drop_database(db_name)

def bootstrap_database(db_name, verbose, source_sql=None):
	frappe.connect(db_name=db_name)
	check_if_ready_for_barracuda()
	import_db_from_sql(source_sql, verbose)
	if not 'tabDefaultValue' in frappe.db.get_tables():
		print('''Database not installed, this can due to lack of permission, or that the database name exists.
			Check your mysql root password, or use --force to reinstall''')
		sys.exit(1)

def import_db_from_sql(source_sql=None, verbose=False):
	if verbose: print("Starting database import...")
	db_name = frappe.conf.db_name
	if not source_sql:
		source_sql = os.path.join(os.path.dirname(__file__), 'framework_mariadb.sql')
	DbManager(frappe.local.db).restore_database(db_name, source_sql, db_name, frappe.conf.db_password)
	if verbose: print("Imported from database %s" % source_sql)

def check_if_ready_for_barracuda():
	mariadb_variables = frappe._dict(frappe.db.sql("""show variables"""))
	mariadb_minor_version = int(mariadb_variables.get('version').split('-')[0].split('.')[1])
	if mariadb_minor_version < 3:
		check_database(mariadb_variables, {
			"innodb_file_format": "Barracuda",
			"innodb_file_per_table": "ON",
			"innodb_large_prefix": "ON"
		})
	check_database(mariadb_variables, {
		"character_set_server": "utf8mb4",
		"collation_server": "utf8mb4_unicode_ci"
	})

def check_database(mariadb_variables, variables_dict):
	mariadb_minor_version = int(mariadb_variables.get('version').split('-')[0].split('.')[1])
	for key, value in variables_dict.items():
		if mariadb_variables.get(key) != value:
			site = frappe.local.site
			msg = ("Creation of your site - {x} failed because MariaDB is not properly {sep}"
				   "configured to use the Barracuda storage engine. {sep}"
				   "Please add the settings below to MariaDB's my.cnf, restart MariaDB then {sep}"
				   "run `bench new-site {x}` again.{sep2}"
				   "").format(x=site, sep2="\n"*2, sep="\n")

			if mariadb_minor_version < 3:
				print_db_config(msg, expected_config_for_barracuda_2)
			else:
				print_db_config(msg, expected_config_for_barracuda_3)
			raise frappe.exceptions.ImproperDBConfigurationError(
				reason="MariaDB default file format is not Barracuda"
			)

def get_root_connection(root_login, root_password):
	import getpass
	if not frappe.local.flags.root_connection:
		if not root_login:
			root_login = 'root'

		if not root_password:
			root_password = frappe.conf.get("root_password") or None

		if not root_password:
			root_password = getpass.getpass("MySQL root password: ")

		frappe.local.flags.root_connection = frappe.database.get_db(user=root_login, password=root_password)

	return frappe.local.flags.root_connection

def print_db_config(explanation, config_text):
	print("="*80)
	print(explanation)
	print(config_text)
	print("="*80)

expected_config_for_barracuda_2 = """
[mysqld]
innodb-file-format=barracuda
innodb-file-per-table=1
innodb-large-prefix=1
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

[mysql]
default-character-set = utf8mb4
"""

expected_config_for_barracuda_3 = """
[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

[mysql]
default-character-set = utf8mb4
"""
