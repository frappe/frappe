from __future__ import unicode_literals

# import warnings
import os, re

import frappe
import subprocess
import psycopg2
import psycopg2.extensions

# cast decimals as floats
DEC2FLOAT = psycopg2.extensions.new_type(
    psycopg2.extensions.DECIMAL.values,
    'DEC2FLOAT',
    lambda value, curs: float(value) if value is not None else None)
psycopg2.extensions.register_type(DEC2FLOAT)

from frappe.database.database import Database
from frappe.model.db_schema import varchar_len

class PostgresDatabase(Database):
	ProgrammingError = psycopg2.ProgrammingError
	OperationalError = psycopg2.OperationalError
	InternalError = psycopg2.InternalError
	SQLError = psycopg2.ProgrammingError
	DataError = psycopg2.DataError
	InterfaceError = psycopg2.InterfaceError

	type_map = {
		'Currency':		('decimal', '18,6'),
		'Int':			('bigint', None),
		'Long Int':		('bigint', None), # convert int to bigint if length is more than 11
		'Float':		('decimal', '18,6'),
		'Percent':		('decimal', '18,6'),
		'Check':		('smallint', None),
		'Small Text':	('text', ''),
		'Long Text':	('text', ''),
		'Code':			('text', ''),
		'Text Editor':	('text', ''),
		'Date':			('date', ''),
		'Datetime':		('timestamp', None),
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

	def get_connection(self):
		# warnings.filterwarnings('ignore', category=psycopg2.Warning)
		conn = psycopg2.connect('host={} dbname={}'.format(self.host, self.user))
		# conn = psycopg2.connect('host={} dbname={} user={} password={}'.format(self.host,
		# 	self.user, self.user, self.password))

		return conn

	def escape(self, s, percent=True):
		"""Excape quotes and percent in given string."""
		# NOTE separating % escape, because % escape should only be done when using LIKE operator
		# or when you use python format string to generate query that already has a %s
		# for example: sql("select name from `tabUser` where name=%s and {0}".format(conditions), something)
		# defaulting it to True, as this is the most frequent use case
		# ideally we shouldn't have to use ESCAPE and strive to pass values via the values argument of sql
		if percent:
			s = s.replace("%", "%%")

		return psycopg2.extensions.QuotedString(s)

	def sql(self, query, *args, **kwargs):
		# replace ` with " for definitions
		query = query.replace('`', '"')

		# select from requires ""
		if re.search('from tab', query, flags=re.IGNORECASE):
			query = re.sub('from tab([a-zA-Z]*)', r'from "tab\1"', query, flags=re.IGNORECASE)

		kwargs['debug'] = True
		return super(PostgresDatabase, self).sql(query, *args, **kwargs)

	def get_tables(self):
		return [d[0] for d in self.sql("""select table_name
			from information_schema.tables
			where table_catalog='{0}'
				and table_type = 'BASE TABLE'
				and table_schema='public'""".format(frappe.conf.db_name))]

	# column type
	def is_type_number(self, code):
		return code == psycopg2.NUMBER

	def is_type_datetime(self, code):
		return code == psycopg2.DATETIME

	# exception type
	def is_deadlocked(self, e):
		return e.pgcode == '40P01'

	def is_timedout(self, e):
		# http://initd.org/psycopg/docs/extensions.html?highlight=datatype#psycopg2.extensions.QueryCanceledError
		return isinstance(e, psycopg2.extensions.QueryCanceledError)

	def is_table_missing(self, e):
		return e.pgcode == '42P01'

	def is_bad_field(self, e):
		return e.pgcode == '42703'

	def is_access_denied(self, e):
		return e.pgcode == '42501'

	def cant_drop_field_or_key(self, e):
		return e.pgcode.startswith('23')

	def create_auth_table(self):
		frappe.db.sql_ddl("""create table if not exists __Auth (
				"doctype" VARCHAR(140) NOT NULL,
				"name" VARCHAR(255) NOT NULL,
				"fieldname" VARCHAR(140) NOT NULL,
				"password" VARCHAR(255) NOT NULL,
				"encrypted" INT NOT NULL DEFAULT 0,
				unique (doctype, name, fieldname)
			)""")

	def create_global_search_table(self):
		if not '__global_search' in frappe.db.get_tables():
			frappe.db.sql('''create table __global_search(
				doctype varchar(100),
				name varchar({0}),
				title varchar({0}),
				content text,
				route varchar({0}),
				published int not null default 0,
				unique (doctype, name))'''.format(varchar_len))

	def create_user_settings_table(self):
		frappe.db.sql_ddl("""create table if not exists __UserSettings (
			"user" VARCHAR(180) NOT NULL,
			"doctype" VARCHAR(180) NOT NULL,
			"data" TEXT,
			UNIQUE("user", "doctype")
			)""")

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
		os.path.join(os.path.dirname(__file__), 'bootstrap_db', 'framework_postgres.sql')])

	frappe.connect()

def get_root_connection():
	return PostgresDatabase(user='postgres')

