import os
<<<<<<< HEAD
=======
import re
>>>>>>> beab110ce9 (fix: clarify error message for child tables)

import frappe
from frappe.database.db_manager import DbManager
from frappe.utils import cint


def setup_database():
<<<<<<< HEAD
	root_conn = get_root_connection(frappe.flags.root_login, frappe.flags.root_password)
=======
	root_conn = get_root_connection()
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	root_conn.commit()
	root_conn.sql("end")
	root_conn.sql(f'DROP DATABASE IF EXISTS "{frappe.conf.db_name}"')

	# If user exists, just update password
<<<<<<< HEAD
	if root_conn.sql(f"SELECT 1 FROM pg_roles WHERE rolname='{frappe.conf.db_name}'"):
		root_conn.sql(f"ALTER USER \"{frappe.conf.db_name}\" WITH PASSWORD '{frappe.conf.db_password}'")
	else:
		root_conn.sql(f"CREATE USER \"{frappe.conf.db_name}\" WITH PASSWORD '{frappe.conf.db_password}'")
	root_conn.sql(f'CREATE DATABASE "{frappe.conf.db_name}"')
	root_conn.sql(f'GRANT ALL PRIVILEGES ON DATABASE "{frappe.conf.db_name}" TO "{frappe.conf.db_name}"')
	if psql_version := root_conn.sql("SHOW server_version_num", as_dict=True):
		semver_version_num = psql_version[0].get("server_version_num") or "140000"
		if cint(semver_version_num) > 150000:
			root_conn.sql(f'ALTER DATABASE "{frappe.conf.db_name}" OWNER TO "{frappe.conf.db_name}"')
=======
	if root_conn.sql(f"SELECT 1 FROM pg_roles WHERE rolname='{frappe.conf.db_user}'"):
		root_conn.sql(f"ALTER USER \"{frappe.conf.db_user}\" WITH PASSWORD '{frappe.conf.db_password}'")
	else:
		root_conn.sql(f"CREATE USER \"{frappe.conf.db_user}\" WITH PASSWORD '{frappe.conf.db_password}'")
	root_conn.sql(f'CREATE DATABASE "{frappe.conf.db_name}"')
	root_conn.sql(f'GRANT ALL PRIVILEGES ON DATABASE "{frappe.conf.db_name}" TO "{frappe.conf.db_user}"')
	if psql_version := root_conn.sql("SHOW server_version_num", as_dict=True):
		semver_version_num = psql_version[0].get("server_version_num") or "140000"
		if cint(semver_version_num) > 150000:
			root_conn.sql(f'ALTER DATABASE "{frappe.conf.db_name}" OWNER TO "{frappe.conf.db_user}"')
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	root_conn.close()


def bootstrap_database(verbose, source_sql=None):
	frappe.connect()
	import_db_from_sql(source_sql, verbose)
<<<<<<< HEAD
	frappe.connect()

=======

	frappe.connect()
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	if "tabDefaultValue" not in frappe.db.get_tables():
		import sys

		from click import secho

		secho(
			"Table 'tabDefaultValue' missing in the restored site. "
			"This happens when the backup fails to restore. Please check that the file is valid\n"
			"Do go through the above output to check the exact error message from MariaDB",
			fg="red",
		)
		sys.exit(1)


def import_db_from_sql(source_sql=None, verbose=False):
	if verbose:
		print("Starting database import...")
	db_name = frappe.conf.db_name
	if not source_sql:
		source_sql = os.path.join(os.path.dirname(__file__), "framework_postgres.sql")
	DbManager(frappe.local.db).restore_database(
<<<<<<< HEAD
		verbose, db_name, source_sql, db_name, frappe.conf.db_password
	)
	if verbose:
		print("Imported from database %s" % source_sql)


def get_root_connection(root_login=None, root_password=None):
	if not frappe.local.flags.root_connection:
		if not root_login:
			root_login = frappe.conf.get("root_login") or None

		if not root_login:
			root_login = input("Enter postgres super user: ")

		if not root_password:
			root_password = frappe.conf.get("root_password") or None

		if not root_password:
			from getpass import getpass

			root_password = getpass("Postgres super user password: ")
=======
		verbose, db_name, source_sql, frappe.conf.db_user, frappe.conf.db_password
	)
	if verbose:
		print("Imported from database {}".format(source_sql))


def get_root_connection():
	if not frappe.local.flags.root_connection:
		import sys
		from getpass import getpass

		if not frappe.flags.root_login:
			frappe.flags.root_login = (
				frappe.conf.get("postgres_root_login")
				or frappe.conf.get("root_login")
				or (sys.__stdin__.isatty() and input("Enter postgres super user [postgres]: "))
				or "postgres"
			)

		if not frappe.flags.root_password:
			frappe.flags.root_password = (
				frappe.conf.get("postgres_root_password")
				or frappe.conf.get("root_password")
				or getpass("Postgres super user password: ")
			)
>>>>>>> beab110ce9 (fix: clarify error message for child tables)

		frappe.local.flags.root_connection = frappe.database.get_db(
			socket=frappe.conf.db_socket,
			host=frappe.conf.db_host,
			port=frappe.conf.db_port,
<<<<<<< HEAD
			user=root_login,
			password=root_password,
			cur_db_name=root_login,
=======
			user=frappe.flags.root_login,
			password=frappe.flags.root_password,
			cur_db_name=frappe.flags.root_login,
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
		)

	return frappe.local.flags.root_connection


<<<<<<< HEAD
def drop_user_and_database(db_name, root_login, root_password):
	root_conn = get_root_connection(
		frappe.flags.root_login or root_login, frappe.flags.root_password or root_password
	)
=======
def drop_user_and_database(db_name, db_user):
	root_conn = get_root_connection()
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
	root_conn.commit()
	root_conn.sql(
		"SELECT pg_terminate_backend (pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = %s",
		(db_name,),
	)
	root_conn.sql("end")
	root_conn.sql(f"DROP DATABASE IF EXISTS {db_name}")
<<<<<<< HEAD
	root_conn.sql(f"DROP USER IF EXISTS {db_name}")
=======
	root_conn.sql(f"DROP USER IF EXISTS {db_user}")
>>>>>>> beab110ce9 (fix: clarify error message for child tables)
