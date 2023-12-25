# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# Database Module
# --------------------
from shutil import which

from frappe.database.database import savepoint


def setup_database(force, verbose=None, no_mariadb_socket=False):
	import frappe

	if frappe.conf.db_type == "postgres":
		import frappe.database.postgres.setup_db

		return frappe.database.postgres.setup_db.setup_database()
	else:
		import frappe.database.mariadb.setup_db

		return frappe.database.mariadb.setup_db.setup_database(
			force, verbose, no_mariadb_socket=no_mariadb_socket
		)


def bootstrap_database(db_name, verbose=None, source_sql=None):
	import frappe

	if frappe.conf.db_type == "postgres":
		import frappe.database.postgres.setup_db

		return frappe.database.postgres.setup_db.bootstrap_database(db_name, verbose, source_sql)
	else:
		import frappe.database.mariadb.setup_db

		return frappe.database.mariadb.setup_db.bootstrap_database(db_name, verbose, source_sql)


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


def get_command(
	host=None, port=None, user=None, password=None, db_name=None, extra=None, dump=False
):
	import frappe

	if frappe.conf.db_type == "postgres":
		if dump:
			bin, bin_name = which("pg_dump"), "pg_dump"
		else:
			bin, bin_name = which("psql"), "psql"

		host = frappe.utils.esc(host, "$ ")
		user = frappe.utils.esc(user, "$ ")
		db_name = frappe.utils.esc(db_name, "$ ")

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
			bin, bin_name = which("mariadb-dump") or which("mysqldump"), "mariadb-dump"
		else:
			bin, bin_name = which("mariadb") or which("mysql"), "mariadb"

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

		if frappe.conf.db_ssl_ca:
			command.extend(
				[
					f"--ssl-ca={frappe.conf.db_ssl_ca}",
				]
			)
			# Check if Two-Way TLS is enabled
			# https://mariadb.com/kb/en/securing-connections-for-client-and-server/#enabling-two-way-tls-for-mariadb-clients
			if frappe.conf.db_ssl_cert and frappe.conf.db_ssl_key:
				command.extend(
					[
						f"--ssl-cert={frappe.conf.db_ssl_cert}",
						f"--ssl-key={frappe.conf.db_ssl_key}"
					]
				)

	return bin, command, bin_name
