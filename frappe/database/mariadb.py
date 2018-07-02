from __future__ import unicode_literals

import sys, os
import frappe
import warnings

from frappe.utils import get_datetime
from frappe.model.db_schema import varchar_len

from pymysql.times import TimeDelta
from pymysql.constants 	import ER, FIELD_TYPE
from pymysql.converters import conversions
import pymysql
import pymysql.err

from frappe.database.database import Database
from frappe.model.db_schema import DbManager

import six

# imports - compatibility imports
from six import (
	binary_type,
	text_type
)

from markdown2 import UnicodeWithAttrs

class MariadbDatabase(Database):
	type_map = {
		'Currency':		('decimal', '18,6'),
		'Int':			('int', '11'),
		'Long Int':		('bigint', '20'), # convert int to bigint if length is more than 11
		'Float':		('decimal', '18,6'),
		'Percent':		('decimal', '18,6'),
		'Check':		('int', '1'),
		'Small Text':	('text', ''),
		'Long Text':	('longtext', ''),
		'Code':			('longtext', ''),
		'Text Editor':	('longtext', ''),
		'Date':			('date', ''),
		'Datetime':		('datetime', '6'),
		'Time':			('time', '6'),
		'Text':			('text', ''),
		'Data':			('varchar', varchar_len),
		'Link':			('varchar', varchar_len),
		'Dynamic Link':	('varchar', varchar_len),
		'Password':		('varchar', varchar_len),
		'Select':		('varchar', varchar_len),
		'Read Only':	('varchar', varchar_len),
		'Attach':		('text', ''),
		'Attach Image':	('text', ''),
		'Signature':	('longtext', ''),
		'Color':		('varchar', varchar_len),
		'Barcode':		('longtext', ''),
		'Geolocation':	('longtext', '')
	}

	ProgrammingError = pymysql.err.ProgrammingError
	OperationalError = pymysql.err.OperationalError
	InternalError = pymysql.err.InternalError
	SQLError = pymysql.err.ProgrammingError
	DataError = pymysql.err.DataError

	def get_connection(self):
		warnings.filterwarnings('ignore', category=pymysql.Warning)
		usessl = 0
		if frappe.conf.db_ssl_ca and frappe.conf.db_ssl_cert and frappe.conf.db_ssl_key:
			usessl = 1
			ssl_params = {
				'ca':frappe.conf.db_ssl_ca,
				'cert':frappe.conf.db_ssl_cert,
				'key':frappe.conf.db_ssl_key
			}

		conversions.update({
			FIELD_TYPE.NEWDECIMAL: float,
			FIELD_TYPE.DATETIME: get_datetime,
			UnicodeWithAttrs: conversions[text_type]
		})

		if six.PY2:
			conversions.update({
				TimeDelta: conversions[binary_type]
			})

		if usessl:
			conn = pymysql.connect(self.host, self.user or '', self.password or '',
				charset='utf8mb4', use_unicode = True, ssl=ssl_params,
				conv = conversions, local_infile = frappe.conf.local_infile)
		else:
			conn = pymysql.connect(self.host, self.user or '', self.password or '',
				charset='utf8mb4', use_unicode = True, conv = conversions,
				local_infile = frappe.conf.local_infile)

		# MYSQL_OPTION_MULTI_STATEMENTS_OFF = 1
		# # self._conn.set_server_option(MYSQL_OPTION_MULTI_STATEMENTS_OFF)

		if self.user != 'root':
			conn.select_db(self.user)

		return conn

	def escape(self, s, percent=True):
		"""Excape quotes and percent in given string."""
		# pymysql expects unicode argument to escape_string with Python 3
		s = frappe.as_unicode(pymysql.escape_string(frappe.as_unicode(s)), "utf-8").replace("`", "\\`")

		# NOTE separating % escape, because % escape should only be done when using LIKE operator
		# or when you use python format string to generate query that already has a %s
		# for example: sql("select name from `tabUser` where name=%s and {0}".format(conditions), something)
		# defaulting it to True, as this is the most frequent use case
		# ideally we shouldn't have to use ESCAPE and strive to pass values via the values argument of sql
		if percent:
			s = s.replace("%", "%%")

		return s

	# column type
	def is_type_number(self, code):
		return code == pymysql.NUMBER

	def is_type_datetime(self, code):
		return code in (pymysql.DATE, pymysql.DATETIME)

	# exception types

	def is_deadlocked(self, e):
		return e.args[0] == ER.LOCK_DEADLOCK

	def is_timedout(self, e):
		return e.args[0] == ER.LOCK_WAIT_TIMEOUT

	def is_table_missing(self, e):
		return e.args[0] == ER.NO_SUCH_TABLE

	def is_missing_column(self, e):
		return e.args[0] == ER.BAD_FIELD_ERROR

	def is_access_denied(self, e):
		return e.args[0] == ER.ACCESS_DENIED_ERROR

	def cant_drop_field_or_key(self, e):
		return e.args[0] == ER.CANT_DROP_FIELD_OR_KEY

	def create_auth_table(self):
		frappe.db.sql_ddl("""create table if not exists __Auth (
				`doctype` VARCHAR(140) NOT NULL,
				`name` VARCHAR(255) NOT NULL,
				`fieldname` VARCHAR(140) NOT NULL,
				`password` VARCHAR(255) NOT NULL,
				`encrypted` INT(1) NOT NULL DEFAULT 0,
				PRIMARY KEY (`doctype`, `name`, `fieldname`)
			) ENGINE=InnoDB ROW_FORMAT=COMPRESSED CHARACTER SET=utf8mb4 COLLATE=utf8mb4_unicode_ci""")

	def create_global_search_table(self):
		if not '__global_search' in frappe.db.get_tables():
			frappe.db.sql('''create table __global_search(
				doctype varchar(100),
				name varchar({0}),
				title varchar({0}),
				content text,
				fulltext(content),
				route varchar({0}),
				published int(1) not null default 0,
				unique `doctype_name` (doctype, name))
				COLLATE=utf8mb4_unicode_ci
				ENGINE=MyISAM
				CHARACTER SET=utf8mb4'''.format(varchar_len))

	def create_user_settings_table(self):
		frappe.db.sql_ddl("""create table if not exists __UserSettings (
			`user` VARCHAR(180) NOT NULL,
			`doctype` VARCHAR(180) NOT NULL,
			`data` TEXT,
			UNIQUE(user, doctype)
			) ENGINE=InnoDB DEFAULT CHARSET=utf8""")

def setup_database(force, verbose):
	frappe.local.session = frappe._dict({'user':'Administrator'})

	db_name = frappe.local.conf.db_name
	root_conn = get_root_connection(frappe.flags.root_login, frappe.flags.root_password)
	dbman = DbManager(root_conn)
	if force or (db_name not in dbman.get_database_list()):
		dbman.delete_user(db_name)
		dbman.drop_database(db_name)
	else:
		raise Exception("Database %s already exists" % (db_name,))

	dbman.create_user(db_name, frappe.conf.db_password)
	if verbose: print("Created user %s" % db_name)

	dbman.create_database(db_name)
	if verbose: print("Created database %s" % db_name)

	dbman.grant_all_privileges(db_name, db_name)
	dbman.flush_privileges()
	if verbose: print("Granted privileges to user %s and database %s" % (db_name, db_name))

	# close root connection
	root_conn.close()

	bootstrap_database(db_name, verbose)

def drop_user_and_database(db_name, root_login, root_password):
	frappe.local.db = get_root_connection(root_login, root_password)
	dbman = DbManager(frappe.local.db)
	dbman.delete_user(db_name)
	dbman.drop_database(db_name)

def bootstrap_database(db_name, verbose):
	frappe.connect(db_name=db_name)
	check_if_ready_for_barracuda()
	import_db_from_sql(None, verbose)
	if not 'tabDefaultValue' in frappe.db.get_tables():
		print('''Database not installed, this can due to lack of permission, or that the database name exists.
Check your mysql root password, or use --force to reinstall''')
		sys.exit(1)

def import_db_from_sql(source_sql=None, verbose=False):
	if verbose: print("Starting database import...")
	db_name = frappe.conf.db_name
	if not source_sql:
		source_sql = os.path.join(os.path.dirname(__file__), 'bootstrap_db', 'framework_mariadb.sql')
	DbManager(frappe.local.db).restore_database(db_name, source_sql, db_name, frappe.conf.db_password)
	if verbose: print("Imported from database %s" % source_sql)

def check_if_ready_for_barracuda():
	mariadb_variables = frappe._dict(frappe.db.sql("""show variables"""))
	mariadb_minor_version = int(mariadb_variables.get('version').split('-')[0].split('.')[1])
	if mariadb_minor_version < 3:
		check_database(mariadb_variables, {
			"innodb_file_format": "Barracuda",
			"innodb_file_per_table": "ON",
			"innodb_large_prefix": "ON"
		})
	check_database(mariadb_variables, {
		"character_set_server": "utf8mb4",
		"collation_server": "utf8mb4_unicode_ci"
	})

def check_database(mariadb_variables, variables_dict):
	mariadb_minor_version = int(mariadb_variables.get('version').split('-')[0].split('.')[1])
	for key, value in variables_dict.items():
		if mariadb_variables.get(key) != value:
			site = frappe.local.site
			msg = ("Creation of your site - {x} failed because MariaDB is not properly {sep}"
				   "configured to use the Barracuda storage engine. {sep}"
				   "Please add the settings below to MariaDB's my.cnf, restart MariaDB then {sep}"
				   "run `bench new-site {x}` again.{sep2}"
				   "").format(x=site, sep2="\n"*2, sep="\n")

			if mariadb_minor_version < 3:
				print_db_config(msg, expected_config_for_barracuda_2)
			else:
				print_db_config(msg, expected_config_for_barracuda_3)
			raise frappe.exceptions.ImproperDBConfigurationError(
				reason="MariaDB default file format is not Barracuda"
			)

def get_root_connection(root_login, root_password):
	import getpass
	if not frappe.local.flags.root_connection:
		if not root_login:
			root_login = 'root'

		if not root_password:
			root_password = frappe.conf.get("root_password") or None

		if not root_password:
			root_password = getpass.getpass("MySQL root password: ")

		frappe.local.flags.root_connection = frappe.database.get_db(user=root_login, password=root_password)

	return frappe.local.flags.root_connection

def print_db_config(explanation, config_text):
	print("="*80)
	print(explanation)
	print(config_text)
	print("="*80)

expected_config_for_barracuda_2 = """[mysqld]
innodb-file-format=barracuda
innodb-file-per-table=1
innodb-large-prefix=1
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

[mysql]
default-character-set = utf8mb4
"""

expected_config_for_barracuda_3 = """[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

[mysql]
default-character-set = utf8mb4
"""
