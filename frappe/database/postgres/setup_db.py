import frappe, subprocess, os
from six.moves import input

def setup_database(force, source_sql=None, verbose=False):
	root_conn = get_root_connection()
	root_conn.commit()
	root_conn.sql("DROP DATABASE IF EXISTS `{0}`".format(frappe.conf.db_name))
	root_conn.sql("DROP USER IF EXISTS {0}".format(frappe.conf.db_name))
	root_conn.sql("CREATE DATABASE `{0}`".format(frappe.conf.db_name))
	root_conn.sql("CREATE user {0} password '{1}'".format(frappe.conf.db_name,
		frappe.conf.db_password))
	root_conn.sql("GRANT ALL PRIVILEGES ON DATABASE `{0}` TO {0}".format(frappe.conf.db_name))
	root_conn.close()

	bootstrap_database(frappe.conf.db_name, verbose, source_sql=source_sql)
	frappe.connect()

def bootstrap_database(db_name, verbose, source_sql=None):
	frappe.connect(db_name=db_name)
	import_db_from_sql(source_sql, verbose)
	frappe.connect(db_name=db_name)
	if 'tabDefaultValue' not in frappe.db.get_tables():
		import sys
		from click import secho

		secho(
			"Table 'tabDefaultValue' missing in the restored site. "
			"This may be due to incorrect permissions or the result of a restore from a bad backup file. "
			"Database not installed correctly.",
			fg="red"
		)
		sys.exit(1)

def import_db_from_sql(source_sql=None, verbose=False):
	if verbose:
		print("Starting Database Import...")

	# we can't pass psql password in arguments in postgresql as mysql. So
	# set password connection parameter in environment variable
	subprocess_env = os.environ.copy()
	subprocess_env['PGPASSWORD'] = str(frappe.conf.db_password)
	# bootstrap db
	if not source_sql:
		source_sql = os.path.join(os.path.dirname(__file__), 'framework_postgres.sql')

	command = [
		'psql', frappe.conf.db_name,
		'-h', frappe.conf.db_host or 'localhost',
		'-p', str(frappe.conf.db_port or '5432'),
		'-U', frappe.conf.db_name,
		'-f', source_sql
	]

	if verbose:
		print(" ".join(command))

	subprocess.check_output(command, env=subprocess_env)

	if verbose:
		print(f"Imported from Database File: {source_sql}")

def setup_help_database(help_db_name):
	root_conn = get_root_connection()
	root_conn.sql("DROP DATABASE IF EXISTS `{0}`".format(help_db_name))
	root_conn.sql("DROP USER IF EXISTS {0}".format(help_db_name))
	root_conn.sql("CREATE DATABASE `{0}`".format(help_db_name))
	root_conn.sql("CREATE user {0} password '{1}'".format(help_db_name, help_db_name))
	root_conn.sql("GRANT ALL PRIVILEGES ON DATABASE `{0}` TO {0}".format(help_db_name))

def get_root_connection(root_login=None, root_password=None):
	import getpass
	if not frappe.local.flags.root_connection:
		if not root_login:
			root_login = frappe.conf.get("root_login") or None

		if not root_login:
			root_login = input("Enter postgres super user: ")

		if not root_password:
			root_password = frappe.conf.get("root_password") or None

		if not root_password:
			root_password = getpass.getpass("Postgres super user password: ")

		frappe.local.flags.root_connection = frappe.database.get_db(user=root_login, password=root_password)

	return frappe.local.flags.root_connection
