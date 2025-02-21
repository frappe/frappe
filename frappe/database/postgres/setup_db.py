import os
import re

import frappe
from frappe.database.db_manager import DbManager
from frappe.utils import cint


def setup_database():
	root_conn = get_root_connection()
	root_conn.commit()
	root_conn.sql("end")
	root_conn.sql(f'DROP DATABASE IF EXISTS "{frappe.conf.db_name}"')

	# If user exists, just update password
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
	root_conn.close()


def bootstrap_database(verbose, source_sql=None):
	frappe.connect()
	import_db_from_sql(source_sql, verbose)

	frappe.connect()
	if "tabDefaultValue" not in frappe.db.get_tables():
		import sys

		from click import secho

		secho(
			"Table 'tabDefaultValue' missing in the restored site. "
			"This happens when the backup fails to restore. Please check that the file is valid\n"
			"Do go through the above output to check the exact error message from Postgres",
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

		frappe.local.flags.root_connection = frappe.database.get_db(
			socket=frappe.conf.db_socket,
			host=frappe.conf.db_host,
			port=frappe.conf.db_port,
			user=frappe.flags.root_login,
			password=frappe.flags.root_password,
			cur_db_name=frappe.flags.root_login,
		)

	return frappe.local.flags.root_connection


def drop_user_and_database(db_name, db_user):
	root_conn = get_root_connection()
	root_conn.commit()
	root_conn.sql(
		"SELECT pg_terminate_backend (pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = %s",
		(db_name,),
	)
	root_conn.sql("end")
	root_conn.sql(f"DROP DATABASE IF EXISTS {db_name}")
	root_conn.sql(f"DROP USER IF EXISTS {db_user}")
