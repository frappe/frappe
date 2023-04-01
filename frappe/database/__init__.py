# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# Database Module
# --------------------
import os

from frappe.database.database import savepoint

def setup_database(force, source_sql=None, verbose=None, socket=None, host=None, port=None, user=None, password=None):
	import frappe

	if frappe.conf.db_type == "postgres":
		import frappe.database.postgres.setup_db

		return frappe.database.postgres.setup_db.setup_database(
			force, socket, host, user, password, port, source_sql, verbose
		)
	else:
		import frappe.database.mariadb.setup_db

		return frappe.database.mariadb.setup_db.setup_database(
			force, socket, host, user, password, port, source_sql, verbose
		)


def drop_user_and_database(db_name, socket=None, host=None, port=None, user=None, password=None):
	import frappe

	if frappe.conf.db_type == "postgres":
		import frappe.database.postgres.setup_db

		return frappe.database.postgres.setup_db.drop_user_and_database(
			db_name, socket, host, user, password, port
		)
	else:
		import frappe.database.mariadb.setup_db

		return frappe.database.mariadb.setup_db.drop_user_and_database(
			db_name, socket, host, user, password, port
		)


def get_db(socket=None, host=None, port=None, user=None, password=None, cur_db_name=None):
	import frappe

	if frappe.conf.db_type == "postgres":
		import frappe.database.postgres.database

		return frappe.database.postgres.database.PostgresDatabase(
			socket=socket,
			host=host,
			port=port,
			user=user,
			password=password,
			cur_db_name=cur_db_name,
		)
	else:
		import frappe.database.mariadb.database

		# Defaults for MySQL
		if not socket:
			socket = os.environ.get('MYSQL_UNIX_PORT')
		if not socket and not host:
			host = '127.0.0.1'
		return frappe.database.mariadb.database.MariaDBDatabase(
			socket=socket,
			host=host,
			port=port,
			user=user,
			password=password,
			cur_db_name=cur_db_name,
		)
