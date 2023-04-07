# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# Database Module
# --------------------
import os
from shutil import which

from frappe.database.database import savepoint


def setup_database(force, source_sql=None, verbose=None, no_mariadb_socket=False):
	import frappe

	if frappe.conf.db_type == "postgres":
		import frappe.database.postgres.setup_db

		return frappe.database.postgres.setup_db.setup_database(force, source_sql, verbose)
	else:
		import frappe.database.mariadb.setup_db

		return frappe.database.mariadb.setup_db.setup_database(
			force, source_sql, verbose, no_mariadb_socket=no_mariadb_socket
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


def get_db(host=None, user=None, password=None, port=None):
	import frappe

	if frappe.conf.db_type == "postgres":
		import frappe.database.postgres.database

		return frappe.database.postgres.database.PostgresDatabase(host, user, password, port=port)
	else:
		import frappe.database.mariadb.database

		return frappe.database.mariadb.database.MariaDBDatabase(host, user, password, port=port)

def get_command(host=None, port=None, user=None, password=None, db_name=None, extra=[], dump=False):
	import frappe
	from frappe.utils import make_esc

	esc = make_esc("$ ")

	if frappe.conf.db_type == "postgres":
		if dump:
			bin = which("pg_dump")
		else:
			bin = which("psql")

		if not host:
			host = '127.0.0.1'
		if not port:
			port = 5432

		conn_string = str
		if password:
			conn_string = f"postgresql://{user}:{password}@{host}:{port}/{db_name}"
		else:
			conn_string = f"postgresql://{user}@{host}:{port}/{db_name}"

		return bin, [esc(conn_string)]

	else:
		if dump:
			bin = which("mysql")
		else:
			bin = which("mysqldump")

		if not host:
			host = '127.0.0.1'
		if not port:
			from frappe.database.mariadb.database import MariaDBDatabase
			port = MariaDBDatabase.default_port

		command = [
			f"--user={user}",
			f"--host={host}",
			f"--port={port}",
		]
		if dump:
			command.extend([
				"--single-transaction",
				"--quick",
				"--lock-tables=false",
    			])
		else:
			command.extend([
				"--pager=less -SFX",
				"--safe-updates",
				"--no-auto-rehash",
			])
		if password:
			command.append(f"--password={password}")

		command.extend(extra)
		command.append(db_name)

		return bin, list(map(esc, command))
