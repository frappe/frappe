import frappe, subprocess, os
from frappe.database.postgres.database import PostgresDatabase

def setup_database(force, verbose):
	root_conn = get_root_connection()
	root_conn.commit()
	root_conn.sql('drop database if exists {0}'.format(frappe.conf.db_name))
	root_conn.sql('drop user if exists {0}'.format(frappe.conf.db_name))
	root_conn.sql('create database {0}'.format(frappe.conf.db_name))
	root_conn.sql("create user {0} password '{1}'".format(frappe.conf.db_name,
		frappe.conf.db_password))
	root_conn.sql('GRANT ALL PRIVILEGES ON DATABASE {0} TO {0}'.format(frappe.conf.db_name))

	# bootstrap db
	subprocess.check_output(['psql', frappe.conf.db_name, '-qf',
		os.path.join(os.path.dirname(__file__), 'framework_postgres.sql')])

	frappe.connect()

def get_root_connection():
	return PostgresDatabase(user='postgres')
