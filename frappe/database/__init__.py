# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# Database Module
# --------------------

from __future__ import unicode_literals

def init_db_session(func):
	"""Configure runtime parameters scoped to the current database connection session.
	"""
	def wrapper(*args, **kwargs):
		import frappe
		conn = func(*args, **kwargs)
		if frappe.conf.db_type == 'postgres' and frappe.local.tenant_id:
			conn.sql(f"SELECT set_config('app.current_tenant', '{frappe.local.tenant_id}', false);")
		return conn
	return wrapper

def setup_database(force, source_sql=None, verbose=None, no_mariadb_socket=False):
	import frappe
	if frappe.conf.db_type == 'postgres':
		import frappe.database.postgres.setup_db
		return frappe.database.postgres.setup_db.setup_database(force, source_sql, verbose)
	else:
		import frappe.database.mariadb.setup_db
		return frappe.database.mariadb.setup_db.setup_database(force, source_sql, verbose, no_mariadb_socket=no_mariadb_socket)

def drop_user_and_database(db_name, root_login=None, root_password=None):
	import frappe
	if frappe.conf.db_type == 'postgres':
		pass
	else:
		import frappe.database.mariadb.setup_db
		return frappe.database.mariadb.setup_db.drop_user_and_database(db_name, root_login, root_password)

@init_db_session
def get_db(host=None, user=None, password=None, port=None):
	import frappe
	if frappe.conf.db_type == 'postgres':
		import frappe.database.postgres.database
		return frappe.database.postgres.database.PostgresDatabase(host, user, password, port=port)
	else:
		import frappe.database.mariadb.database
		return frappe.database.mariadb.database.MariaDBDatabase(host, user, password, port=port)

def setup_help_database(help_db_name):
	import frappe
	if frappe.conf.db_type == 'postgres':
		import frappe.database.postgres.setup_db
		return frappe.database.postgres.setup_db.setup_help_database(help_db_name)
	else:
		import frappe.database.mariadb.setup_db
		return frappe.database.mariadb.setup_db.setup_help_database(help_db_name)
