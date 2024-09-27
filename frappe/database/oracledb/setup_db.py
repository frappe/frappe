import os
import re

import frappe
# from frappe.database.db_manager import DbManager

from frappe.database.oracledb.database import OracleDbManager as DbManager
from frappe.utils import cint


def setup_database():
	root_conn = get_root_connection()
	root_conn.autocommit = True
	cursor = root_conn.get_cursor()

	# Drop the user if it exists along with its schema
	if cursor.execute(
		f"SELECT 1 FROM all_users WHERE username = '{frappe.conf.db_user.upper()}'").fetchone():
		cursor.execute(f"DROP USER {frappe.conf.db_user} CASCADE")

	# Create user and grant privileges
	query = f'CREATE USER {frappe.conf.db_user} IDENTIFIED BY "{frappe.conf.db_password}"'
	cursor.execute(query)
	cursor.execute(f"GRANT CONNECT, RESOURCE, DBA TO {frappe.conf.db_user}")

	# Create schema
	cursor.execute(f"ALTER SESSION SET CURRENT_SCHEMA = {frappe.conf.db_user}")
	cursor.close()


def get_root_connection():
	if not frappe.local.flags.root_connection:
		from getpass import getpass

		if not frappe.flags.root_login:
			frappe.flags.root_login = (
				frappe.conf.get("root_login")
				or input("Enter oracledb super user [system]: ")
				or "system"
			)

		if not frappe.flags.root_password:
			frappe.flags.root_password = (
				frappe.conf.get("root_password")
				or getpass("Oracle super user password: ")
			)

		frappe.local.flags.root_connection = frappe.database.get_db(
			socket=frappe.conf.db_socket,
			host=frappe.conf.db_host,
			port=frappe.conf.db_port,
			user=frappe.flags.root_login,
			password=frappe.flags.root_password,
			cur_db_name=frappe.flags.root_login,
			service_name=frappe.conf.db_service_name
		)

	return frappe.local.flags.root_connection


def bootstrap_database(verbose, source_sql=None):
	frappe.connect()
	import_db_from_sql(source_sql, verbose)

	frappe.connect()
	if "tabDefaultValue" not in frappe.db.get_tables():
		import sys

		from click import secho

		secho(
			"Table 'tabDefaultValue' missing in the restored site. "
			"This may be due to incorrect permissions or the result of a restore from a bad backup file. "
			"Database not installed correctly.",
			fg="red",
		)
		sys.exit(1)


def import_db_from_sql(source_sql=None, verbose=False):
	if verbose:
		print("Starting database import...")
	db_name = frappe.conf.db_name
	if not source_sql:
		source_sql = os.path.join(os.path.dirname(__file__), "framework_oracledb.sql")
	DbManager(frappe.local.db).restore_database(
		verbose, db_name, source_sql, frappe.conf.db_user, frappe.conf.db_password,
		frappe.conf.db_service_name
	)
	if verbose:
		print("Imported from database %s" % source_sql)
