import os

import frappe
from frappe import _


def setup_database():
	root_conn = get_root_connection(frappe.flags.root_login, frappe.flags.root_password)
	root_conn.commit()
	root_conn.sql("end")
	root_conn.sql(f"DROP DATABASE IF EXISTS `{frappe.conf.db_name}`")
	root_conn.sql(f"DROP USER IF EXISTS {frappe.conf.db_name}")
	root_conn.sql(f"CREATE DATABASE `{frappe.conf.db_name}`")
	root_conn.sql(f"CREATE user {frappe.conf.db_name} password '{frappe.conf.db_password}'")
	root_conn.sql("GRANT ALL PRIVILEGES ON DATABASE `{0}` TO {0}".format(frappe.conf.db_name))
	root_conn.close()


def bootstrap_database(db_name, verbose, source_sql=None):
	frappe.connect(db_name=db_name)
	import_db_from_sql(source_sql, verbose)
	frappe.connect(db_name=db_name)

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
	import shlex
	from shutil import which

	from frappe.database import get_command
	from frappe.utils import execute_in_shell

	# bootstrap db
	if not source_sql:
		source_sql = os.path.join(os.path.dirname(__file__), "framework_postgres.sql")

	pv = which("pv")

	command = []

	if source_sql.endswith(".gz"):
		if gzip := which("gzip"):
			source = []
			if pv:
				command.extend([gzip, "-cd", source_sql, "|", pv, "|"])
			else:
				command.extend([gzip, "-cd", source_sql, "|"])
		else:
			raise Exception("`gzip` not installed")
	else:
		if pv:
			command.extend([pv, source_sql, "|"])
			source = []
			print("Restoring Database file...")
		else:
			source = ["-f", source_sql]

	bin, args, bin_name = get_command(
		host=frappe.conf.db_host,
		port=frappe.conf.db_port,
		user=frappe.conf.db_name,
		password=frappe.conf.db_password,
		db_name=frappe.conf.db_name,
	)

	if not bin:
		frappe.throw(
			_("{} not found in PATH! This is required to restore the database.").format(bin_name),
			exc=frappe.ExecutableNotFound,
		)
	command.append(bin)
	command.append(shlex.join(args))
	command.extend(source)
	execute_in_shell(" ".join(command), check_exit_code=True, verbose=verbose)
	frappe.cache.delete_keys("")  # Delete all keys associated with this site.


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

		frappe.local.flags.root_connection = frappe.database.get_db(
			host=frappe.conf.db_host,
			port=frappe.conf.db_port,
			user=root_login,
			password=root_password,
		)

	return frappe.local.flags.root_connection


def drop_user_and_database(db_name, root_login, root_password):
	root_conn = get_root_connection(
		frappe.flags.root_login or root_login, frappe.flags.root_password or root_password
	)
	root_conn.commit()
	root_conn.sql(
		"SELECT pg_terminate_backend (pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = %s",
		(db_name,),
	)
	root_conn.sql("end")
	root_conn.sql(f"DROP DATABASE IF EXISTS {db_name}")
	root_conn.sql(f"DROP USER IF EXISTS {db_name}")
