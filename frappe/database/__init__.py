# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# Database Module
# --------------------
import os
from shutil import which

from frappe.database.database import savepoint


def setup_database(force, source_sql, verbose, root_login, root_password, no_mariadb_socket=False):
	import frappe

	if frappe.conf.db_type == "postgres":
		import frappe.database.postgres.setup_db

		return frappe.database.postgres.setup_db.setup_database(
			force, source_sql, verbose, root_login, root_password
		)
	else:
		import frappe.database.mariadb.setup_db

		return frappe.database.mariadb.setup_db.setup_database(
			force, source_sql, verbose, root_login, root_password, no_mariadb_socket=no_mariadb_socket
		)


def drop_user_and_database(db_name, root_login=None, root_password=None):
	import frappe

	if frappe.conf.db_type == "postgres":
		import frappe.database.postgres.setup_db

		return frappe.database.postgres.setup_db.drop_user_and_database(
			db_name, root_login, root_password
		)
	else:
		import frappe.database.mariadb.setup_db

		return frappe.database.mariadb.setup_db.drop_user_and_database(
			db_name, root_login, root_password
		)


def get_db(host, port, user, password, dbname):
	import frappe

	if frappe.conf.db_type == "postgres":
		import frappe.database.postgres.database

		return frappe.database.postgres.database.PostgresDatabase(host, user, password, port, dbname)
	else:
		import frappe.database.mariadb.database

		return frappe.database.mariadb.database.MariaDBDatabase(host, user, password, port, dbname)


def get_command(
	host=None, port=None, user=None, password=None, db_name=None, extra=None, dump=False
):
	import frappe

	if frappe.conf.db_type == "postgres":
		if dump:
			bin, bin_name = which("pg_dump"), "pg_dump"
		else:
			bin, bin_name = which("psql"), "psql"

		if not host:
			host = "127.0.0.1"
		if not port:
			port = 5432

		host = frappe.utils.esc(host, "$ ")
		user = frappe.utils.esc(user, "$ ")
		db_name = frappe.utils.esc(db_name, "$ ")

		conn_string = str
		if password:
			password = frappe.utils.esc(password, "$ ")
			conn_string = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
		else:
			conn_string = f"postgresql://{user}@{host}:{port}/{db_name}"

		command = [conn_string]

		if extra:
			command.extend(extra)

	else:
		if dump:
			bin, bin_name = which("mysqldump"), "mysqldump"
		else:
			bin, bin_name = which("mysql"), "mysql"

		if not host:
			host = "127.0.0.1"
		if not port:
			from frappe.database.mariadb.database import MariaDBDatabase

			port = MariaDBDatabase.default_port

		host = frappe.utils.esc(host, "$ ")
		user = frappe.utils.esc(user, "$ ")
		db_name = frappe.utils.esc(db_name, "$ ")

		command = [
			f"--user={user}",
			f"--host={host}",
			f"--port={port}",
		]

		if password:
			password = frappe.utils.esc(password, "$ ")
			command.append(f"--password={password}")

		if dump:
			command.extend(
				[
					"--single-transaction",
					"--quick",
					"--lock-tables=false",
				]
			)
		else:
			command.extend(
				[
					"--pager=less -SFX",
					"--safe-updates",
					"--no-auto-rehash",
				]
			)

		command.append(db_name)

		if extra:
			command.extend(extra)

	return bin, command, bin_name
