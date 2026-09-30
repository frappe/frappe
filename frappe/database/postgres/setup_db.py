import os
import re
from contextlib import contextmanager

from psycopg2 import sql

import frappe
from frappe.database.db_manager import DbManager
from frappe.utils import cint


def setup_database():
	root_conn = get_root_connection()
	root_conn.commit()
	root_conn.sql("end")
	postgres_version = _get_server_version(root_conn)
	_drop_database(root_conn, frappe.conf.db_name, postgres_version)

	# If user exists, just update password
	if root_conn.sql(f"SELECT 1 FROM pg_roles WHERE rolname='{frappe.conf.db_user}'"):
		root_conn.sql(f"ALTER USER \"{frappe.conf.db_user}\" WITH PASSWORD '{frappe.conf.db_password}'")
	else:
		root_conn.sql(f"CREATE USER \"{frappe.conf.db_user}\" WITH PASSWORD '{frappe.conf.db_password}'")
	root_conn.sql(f'CREATE DATABASE "{frappe.conf.db_name}"')
	root_conn.sql(f'GRANT ALL PRIVILEGES ON DATABASE "{frappe.conf.db_name}" TO "{frappe.conf.db_user}"')
	if postgres_version > 150000:
		_set_database_owner(root_conn, frappe.conf.db_name, frappe.conf.db_user, postgres_version)
	root_conn.close()

	# On Azure Managed PostgreSQL the public schema is owned by the azure_pg_admin role.
	# Because the schema owner is hard-coded to be azure_pg_admin by Azure,
	# changing the database owner no longer changes the schema owner (cascade).
	db_conn = frappe.database.get_db(
		socket=frappe.conf.db_socket,
		host=frappe.conf.db_host,
		port=frappe.conf.db_port,
		user=frappe.flags.root_login,
		password=frappe.flags.root_password,
		cur_db_name=frappe.conf.db_name,  # Connect to the new database to grant permissions on the public schema
	)
	try:
		db_conn.commit()
		db_conn.sql("end")
		db_conn.sql(f'GRANT ALL ON SCHEMA {db_conn.db_schema} TO "{frappe.conf.db_user}"')
		db_conn.sql("end")  # persist the schema grant before the best-effort setup below
		# Best-effort setup for the Postgres Query Stats report: skip silently if the extension
		# is unavailable or the root role cannot create it.
		try:
			db_conn.sql("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
			db_conn.sql("end")
		except Exception:
			db_conn.rollback()
	finally:
		db_conn.close()


def _get_server_version(root_conn) -> int:
	return cint(root_conn.sql("SHOW server_version_num", pluck=True)[0])


def _drop_database(root_conn, db_name: str, postgres_version: int) -> None:
	owner = root_conn.sql(
		"SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s", (db_name,), pluck=True
	)
	if not owner:
		return

	# Only the owner can drop a database; a managed root may have handed ownership to the site role.
	with _temporary_role_access(root_conn, owner[0], "USAGE", postgres_version):
		root_conn.execute_query(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(db_name)))


def _set_database_owner(root_conn, db_name: str, db_user: str, postgres_version: int) -> None:
	role_privilege = "SET" if postgres_version >= 160000 else "MEMBER"
	with _temporary_role_access(root_conn, db_user, role_privilege, postgres_version):
		root_conn.execute_query(
			sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
				sql.Identifier(db_name),
				sql.Identifier(db_user),
			)
		)


@contextmanager
def _temporary_role_access(root_conn, role: str, privilege: str, postgres_version: int):
	"""Grant `role` to the current user for the block if it lacks `privilege` on it."""
	has_privilege = root_conn.sql(
		"SELECT pg_has_role(current_user, %s, %s)",
		(role, privilege),
		pluck=True,
	)
	needs_role_access = not has_privilege or not has_privilege[0]

	if needs_role_access:
		grant, restore = _get_temporary_role_statements(root_conn, role, privilege, postgres_version)
		root_conn.execute_query(grant)

	try:
		yield
	finally:
		if needs_role_access:
			root_conn.execute_query(restore)


def _get_temporary_role_statements(
	root_conn, role: str, privilege: str, postgres_version: int
) -> tuple[sql.Composed, sql.Composed]:
	grant = sql.SQL("GRANT {} TO current_user").format(sql.Identifier(role))
	restore = sql.SQL("REVOKE {} FROM current_user").format(sql.Identifier(role))
	if postgres_version < 160000:
		return grant, restore

	# SET allows SET ROLE; INHERIT passes on the role's privileges, such as database ownership.
	option = "INHERIT" if privilege == "USAGE" else "SET"
	# A role can already hold a self-grant without this option.
	# Only restore grants made by this user; grants from other users remain untouched.
	existing_self_grant = root_conn.sql(
		"""SELECT 1 FROM pg_auth_members membership
		JOIN pg_roles member_role ON member_role.oid = membership.member
		JOIN pg_roles target_role ON target_role.oid = membership.roleid
		WHERE target_role.rolname = %s AND member_role.rolname = current_user
			AND membership.grantor = membership.member""",
		(role,),
		pluck=True,
	)
	if existing_self_grant:
		restore = grant + sql.SQL(f" WITH {option} FALSE")
	return grant + sql.SQL(f" WITH {option} TRUE"), restore


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
	_drop_database(root_conn, db_name, _get_server_version(root_conn))
	root_conn.execute_query(sql.SQL("DROP USER IF EXISTS {}").format(sql.Identifier(db_user)))
