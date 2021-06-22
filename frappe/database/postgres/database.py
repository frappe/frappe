import re
import frappe
import psycopg2
import psycopg2.extensions
from six import string_types
from frappe.utils import cstr
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from frappe.database.database import Database
from frappe.database.postgres.schema import PostgresTable

# cast decimals as floats
DEC2FLOAT = psycopg2.extensions.new_type(
    psycopg2.extensions.DECIMAL.values,
    'DEC2FLOAT',
    lambda value, curs: float(value) if value is not None else None)

psycopg2.extensions.register_type(DEC2FLOAT)

class PostgresDatabase(Database):
	ProgrammingError = psycopg2.ProgrammingError
	TableMissingError = psycopg2.ProgrammingError
	OperationalError = psycopg2.OperationalError
	InternalError = psycopg2.InternalError
	SQLError = psycopg2.ProgrammingError
	DataError = psycopg2.DataError
	InterfaceError = psycopg2.InterfaceError
	REGEX_CHARACTER = '~'

	def setup_type_map(self):
		self.db_type = 'postgres'
		self.type_map = {
			'Currency':		('decimal', '18,6'),
			'Int':			('bigint', None),
			'Long Int':		('bigint', None),
			'Float':		('decimal', '18,6'),
			'Percent':		('decimal', '18,6'),
			'Check':		('smallint', None),
			'Small Text':	('text', ''),
			'Long Text':	('text', ''),
			'Code':			('text', ''),
			'Text Editor':	('text', ''),
			'Markdown Editor':	('text', ''),
			'HTML Editor':	('text', ''),
			'Date':			('date', ''),
			'Datetime':		('timestamp', None),
			'Time':			('time', '6'),
			'Text':			('text', ''),
			'Data':			('varchar', self.VARCHAR_LEN),
			'Link':			('varchar', self.VARCHAR_LEN),
			'Dynamic Link':	('varchar', self.VARCHAR_LEN),
			'Password':		('text', ''),
			'Select':		('varchar', self.VARCHAR_LEN),
			'Rating':		('smallint', None),
			'Read Only':	('varchar', self.VARCHAR_LEN),
			'Attach':		('text', ''),
			'Attach Image':	('text', ''),
			'Signature':	('text', ''),
			'Color':		('varchar', self.VARCHAR_LEN),
			'Barcode':		('text', ''),
			'Geolocation':	('text', ''),
			'Duration':		('decimal', '18,6')
		}

	def get_connection(self):
		conn = psycopg2.connect("host='{}' dbname='{}' user='{}' password='{}' port={}".format(
			self.host, self.user, self.user, self.password, self.port
		))
		conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT) # TODO: Remove this

		return conn

	def escape(self, s, percent=True):
		"""Excape quotes and percent in given string."""
		if isinstance(s, bytes):
			s = s.decode('utf-8')

		if percent:
			s = s.replace("%", "%%")

		s = s.encode('utf-8')

		return str(psycopg2.extensions.QuotedString(s))

	def get_database_size(self):
		''''Returns database size in MB'''
		db_size = self.sql("SELECT (pg_database_size(%s) / 1024 / 1024) as database_size",
			self.db_name, as_dict=True)
		return db_size[0].get('database_size')

	# pylint: disable=W0221
	def sql(self, *args, **kwargs):
		if args:
			# since tuple is immutable
			args = list(args)
			args[0] = modify_query(args[0])
			args = tuple(args)
		elif kwargs.get('query'):
			kwargs['query'] = modify_query(kwargs.get('query'))

		return super(PostgresDatabase, self).sql(*args, **kwargs)

	def get_tables(self):
		return [d[0] for d in self.sql("""select table_name
			from information_schema.tables
			where table_catalog='{0}'
				and table_type = 'BASE TABLE'
				and table_schema='{1}'""".format(frappe.conf.db_name, frappe.conf.get("db_schema", "public")))]

	def format_date(self, date):
		if not date:
			return '0001-01-01'

		if not isinstance(date, frappe.string_types):
			date = date.strftime('%Y-%m-%d')

		return date

	# column type
	@staticmethod
	def is_type_number(code):
		return code == psycopg2.NUMBER

	@staticmethod
	def is_type_datetime(code):
		return code == psycopg2.DATETIME

	# exception type
	@staticmethod
	def is_deadlocked(e):
		return e.pgcode == '40P01'

	@staticmethod
	def is_timedout(e):
		# http://initd.org/psycopg/docs/extensions.html?highlight=datatype#psycopg2.extensions.QueryCanceledError
		return isinstance(e, psycopg2.extensions.QueryCanceledError)

	@staticmethod
	def is_table_missing(e):
		return getattr(e, 'pgcode', None) == '42P01'

	@staticmethod
	def is_missing_column(e):
		return getattr(e, 'pgcode', None) == '42703'

	@staticmethod
	def is_access_denied(e):
		return e.pgcode == '42501'

	@staticmethod
	def cant_drop_field_or_key(e):
		return e.pgcode.startswith('23')

	@staticmethod
	def is_duplicate_entry(e):
		return e.pgcode == '23505'

	@staticmethod
	def is_primary_key_violation(e):
		return e.pgcode == '23505' and '_pkey' in cstr(e.args[0])

	@staticmethod
	def is_unique_key_violation(e):
		return e.pgcode == '23505' and '_key' in cstr(e.args[0])

	@staticmethod
	def is_duplicate_fieldname(e):
		return e.pgcode == '42701'

	@staticmethod
	def is_data_too_long(e):
		return e.pgcode == '22001'

	def create_auth_table(self):
		self.sql_ddl("""create table if not exists "__Auth" (
				"doctype" VARCHAR(140) NOT NULL,
				"name" VARCHAR(255) NOT NULL,
				"fieldname" VARCHAR(140) NOT NULL,
				"password" TEXT NOT NULL,
				"encrypted" INT NOT NULL DEFAULT 0,
				PRIMARY KEY ("doctype", "name", "fieldname")
			)""")

	def create_global_search_table(self):
		if not '__global_search' in self.get_tables():
			self.sql('''create table "__global_search"(
				doctype varchar(100),
				name varchar({0}),
				title varchar({0}),
				content text,
				route varchar({0}),
				published int not null default 0,
				unique (doctype, name))'''.format(self.VARCHAR_LEN))

	def create_user_settings_table(self):
		self.sql_ddl("""create table if not exists "__UserSettings" (
			"user" VARCHAR(180) NOT NULL,
			"doctype" VARCHAR(180) NOT NULL,
			"data" TEXT,
			UNIQUE ("user", "doctype")
			)""")

	def create_help_table(self):
		self.sql('''CREATE TABLE "help"(
				"path" varchar(255),
				"content" text,
				"title" text,
				"intro" text,
				"full_path" text)''')
		self.sql('''CREATE INDEX IF NOT EXISTS "help_index" ON "help" ("path")''')

	def updatedb(self, doctype, meta=None):
		"""
		Syncs a `DocType` to the table
		* creates if required
		* updates columns
		* updates indices
		"""
		res = self.sql("select issingle from `tabDocType` where name='{}'".format(doctype))
		if not res:
			raise Exception('Wrong doctype {0} in updatedb'.format(doctype))

		if not res[0][0]:
			db_table = PostgresTable(doctype, meta)
			db_table.validate()

			self.commit()
			db_table.sync()
			self.begin()

	@staticmethod
	def get_on_duplicate_update(key='name'):
		if isinstance(key, list):
			key = '", "'.join(key)
		return 'ON CONFLICT ("{key}") DO UPDATE SET '.format(
			key=key
		)

	def check_transaction_status(self, query):
		pass

	def has_index(self, table_name, index_name):
		return self.sql("""SELECT 1 FROM pg_indexes WHERE tablename='{table_name}'
			and indexname='{index_name}' limit 1""".format(table_name=table_name, index_name=index_name))

	def add_index(self, doctype, fields, index_name=None):
		"""Creates an index with given fields if not already created.
		Index name will be `fieldname1_fieldname2_index`"""
		index_name = index_name or self.get_index_name(fields)
		table_name = 'tab' + doctype

		self.commit()
		self.sql("""CREATE INDEX IF NOT EXISTS "{}" ON `{}`("{}")""".format(index_name, table_name, '", "'.join(fields)))

	def add_unique(self, doctype, fields, constraint_name=None):
		if isinstance(fields, string_types):
			fields = [fields]
		if not constraint_name:
			constraint_name = "unique_" + "_".join(fields)

		if not self.sql("""
			SELECT CONSTRAINT_NAME
			FROM information_schema.TABLE_CONSTRAINTS
			WHERE table_name=%s
			AND constraint_type='UNIQUE'
			AND CONSTRAINT_NAME=%s""",
			('tab' + doctype, constraint_name)):
				self.commit()
				self.sql("""ALTER TABLE `tab%s`
					ADD CONSTRAINT %s UNIQUE (%s)""" % (doctype, constraint_name, ", ".join(fields)))

	def get_table_columns_description(self, table_name):
		"""Returns list of column and its description"""
		# pylint: disable=W1401
		return self.sql('''
			SELECT a.column_name AS name,
			CASE LOWER(a.data_type)
				WHEN 'character varying' THEN CONCAT('varchar(', a.character_maximum_length ,')')
				WHEN 'timestamp without time zone' THEN 'timestamp'
				ELSE a.data_type
			END AS type,
			COUNT(b.indexdef) AS Index,
			SPLIT_PART(COALESCE(a.column_default, NULL), '::', 1) AS default,
			BOOL_OR(b.unique) AS unique
			FROM information_schema.columns a
			LEFT JOIN
				(SELECT indexdef, tablename, indexdef LIKE '%UNIQUE INDEX%' AS unique
					FROM pg_indexes
					WHERE tablename='{table_name}') b
					ON SUBSTRING(b.indexdef, '\(.*\)') LIKE CONCAT('%', a.column_name, '%')
			WHERE a.table_name = '{table_name}'
			GROUP BY a.column_name, a.data_type, a.column_default, a.character_maximum_length;'''
			.format(table_name=table_name), as_dict=1)

	def get_database_list(self, target):
		return [d[0] for d in self.sql("SELECT datname FROM pg_database;")]

def modify_query(query):
	""""Modifies query according to the requirements of postgres"""
	# replace ` with " for definitions
	query = query.replace('`', '"')
	query = replace_locate_with_strpos(query)
	# select from requires ""
	if re.search('from tab', query, flags=re.IGNORECASE):
		query = re.sub('from tab([a-zA-Z]*)', r'from "tab\1"', query, flags=re.IGNORECASE)

	return query

def replace_locate_with_strpos(query):
	# strpos is the locate equivalent in postgres
	if re.search(r'locate\(', query, flags=re.IGNORECASE):
		query = re.sub(r'locate\(([^,]+),([^)]+)\)', r'strpos(\2, \1)', query, flags=re.IGNORECASE)
	return query
