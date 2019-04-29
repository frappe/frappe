import frappe, subprocess, os

def setup_database(force, source_sql, verbose):
	root_conn = get_root_connection()
	root_conn.commit()
	root_conn.sql("DROP DATABASE IF EXISTS `{0}`".format(frappe.conf.db_name))
	root_conn.sql("DROP USER IF EXISTS {0}".format(frappe.conf.db_name))
	root_conn.sql("CREATE DATABASE `{0}`".format(frappe.conf.db_name))
	root_conn.sql("CREATE user {0} password '{1}'".format(frappe.conf.db_name,
		frappe.conf.db_password))
	root_conn.sql("GRANT ALL PRIVILEGES ON DATABASE `{0}` TO {0}".format(frappe.conf.db_name))

	# bootstrap db
	subprocess.check_output(['psql', frappe.conf.db_name, '-qf',
		os.path.join(os.path.dirname(__file__), 'framework_postgres.sql')])

	frappe.connect()

def setup_help_database(help_db_name):
	root_conn = get_root_connection()
	root_conn.sql("DROP DATABASE IF EXISTS `{0}`".format(help_db_name))
	root_conn.sql("DROP USER IF EXISTS {0}".format(help_db_name))
	root_conn.sql("CREATE DATABASE `{0}`".format(help_db_name))
	root_conn.sql("CREATE user {0} password '{1}'".format(help_db_name, help_db_name))
	root_conn.sql("GRANT ALL PRIVILEGES ON DATABASE `{0}` TO {0}".format(help_db_name))

def get_root_connection(root_login='postgres', root_password=None):
	import getpass
	if not frappe.local.flags.root_connection:
		if not root_login:
			root_login = 'root'

		if not root_password:
			root_password = frappe.conf.get("root_password") or None

		if not root_password:
			root_password = getpass.getpass("Postgres root password: ")

		frappe.local.flags.root_connection = frappe.database.get_db(user=root_login, password=root_password)

	return frappe.local.flags.root_connection
