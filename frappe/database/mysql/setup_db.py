from __future__ import unicode_literals

import frappe
import os, sys
from frappe.database.db_manager import DbManager

def setup_database(force, source_sql, verbose, no_mysql_socket=False):
	frappe.local.session = frappe._dict({'user':'Administrator'})

	db_name = frappe.local.conf.db_name
	root_conn = get_root_connection(frappe.flags.root_login, frappe.flags.root_password)
	dbman = DbManager(root_conn)
	if force or (db_name not in dbman.get_database_list()):
		dbman.delete_user(db_name)
		if no_mysql_socket:
			dbman.delete_user(db_name, host="%")
		dbman.drop_database(db_name)
	else:
		raise Exception("Database %s already exists" % (db_name,))

	dbman.create_user(db_name, frappe.conf.db_password)
	if no_mysql_socket:
		dbman.create_user(db_name, frappe.conf.db_password, host="%")
	if verbose: print("Created user %s" % db_name)

	dbman.create_database(db_name)
	if verbose: print("Created database %s" % db_name)

	dbman.grant_all_privileges(db_name, db_name)
	if no_mysql_socket:
		dbman.grant_all_privileges(db_name, db_name, host="%")
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
	dbman.delete_user(db_name, host="%")
	dbman.delete_user(db_name)
	dbman.drop_database(db_name)

def bootstrap_database(db_name, verbose, source_sql=None):
	frappe.connect(db_name=db_name)
	if not check_database_settings():
		print('Database settings do not match expected values; stopping database setup.')
		sys.exit(1)

	import_db_from_sql(source_sql, verbose)

	frappe.connect(db_name=db_name)
	if not 'tabDefaultValue' in frappe.db.get_tables():
		print('''Database not installed, this can due to lack of permission, or that the database name exists.
			Check your mysql root password, or use --force to reinstall''')
		sys.exit(1)

def import_db_from_sql(source_sql=None, verbose=False):
	if verbose: print("Starting database import...")
	db_name = frappe.conf.db_name
	if not source_sql:
		source_sql = os.path.join(os.path.dirname(__file__), 'framework_mysql.sql')
	DbManager(frappe.local.db).restore_database(db_name, source_sql, db_name, frappe.conf.db_password)
	if verbose: print("Imported from database %s" % source_sql)


def check_database_settings():
	expected_variables = {
		"character_set_server": "utf8mb4",
		"collation_server": "utf8mb4_unicode_ci"
	}

	mysql_variables = frappe._dict(frappe.db.sql("""show variables"""))
	# Check each expected value vs. actuals:
	result = True
	for key, expected_value in expected_variables.items():
		if mysql_variables.get(key) != expected_value:
			print("For key %s. Expected value %s, found value %s" %
				  (key, expected_value, mysql_variables.get(key)))
			result = False
	if not result:
		site = frappe.local.site
		msg = ("Creation of your site - {x} failed because mysql is not properly {sep}"
			   "configured."
			   "the Barracuda storage engine. {sep}{sep}"
			   "Please verify the settings above in mysql's my.cnf.  Restart mysql.  And {sep}"
			   "then run `bench new-site {x}` again.{sep2}"
			   "").format(x=site, sep2="\n"*2, sep="\n")
		print_db_config(msg)
	return result


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


def print_db_config(explanation):
	print("="*80)
	print(explanation)
	print("="*80)
