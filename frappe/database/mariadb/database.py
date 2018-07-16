from __future__ import unicode_literals

import frappe
import sys, os
import warnings

import pymysql
from pymysql.times import TimeDelta
from pymysql.constants 	import ER, FIELD_TYPE
from pymysql.converters import conversions

from frappe.utils import get_datetime
from markdown2 import UnicodeWithAttrs
from six import PY2, binary_type, text_type
from frappe.database.database import Database
from frappe.database.mariadb.schema import MariaDBTable


# imports - compatibility imports


class MariaDBDatabase(Database):
	ProgrammingError = pymysql.err.ProgrammingError
	OperationalError = pymysql.err.OperationalError
	InternalError = pymysql.err.InternalError
	SQLError = pymysql.err.ProgrammingError
	DataError = pymysql.err.DataError

	def setup_type_map(self):
		self.type_map = {
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
			'Data':			('varchar', self.VARCHAR_LEN),
			'Link':			('varchar', self.VARCHAR_LEN),
			'Dynamic Link':	('varchar', self.VARCHAR_LEN),
			'Password':		('varchar', self.VARCHAR_LEN),
			'Select':		('varchar', self.VARCHAR_LEN),
			'Read Only':	('varchar', self.VARCHAR_LEN),
			'Attach':		('text', ''),
			'Attach Image':	('text', ''),
			'Signature':	('longtext', ''),
			'Color':		('varchar', self.VARCHAR_LEN),
			'Barcode':		('longtext', ''),
			'Geolocation':	('longtext', '')
		}

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

		if PY2:
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

		return "'" + s + "'"

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
				CHARACTER SET=utf8mb4'''.format(self.VARCHAR_LEN))

	def create_user_settings_table(self):
		frappe.db.sql_ddl("""create table if not exists __UserSettings (
			`user` VARCHAR(180) NOT NULL,
			`doctype` VARCHAR(180) NOT NULL,
			`data` TEXT,
			UNIQUE(user, doctype)
			) ENGINE=InnoDB DEFAULT CHARSET=utf8""")

	def get_on_duplicate_update(self, key=None):
		return 'ON DUPLICATE key UPDATE '

	def get_indexes_for(self, table_name):
		pass

	def updatedb(self, doctype, meta=None):
		"""
		Syncs a `DocType` to the table
		* creates if required
		* updates columns
		* updates indices
		"""
		res = frappe.db.sql("select issingle from `tabDocType` where name=%s", (doctype,))
		if not res:
			raise Exception('Wrong doctype {0} in updatedb'.format(doctype))

		if not res[0][0]:
			db_table = MariaDBTable(doctype, meta)
			db_table.validate()

			frappe.db.commit()
			db_table.sync()
			frappe.db.begin()