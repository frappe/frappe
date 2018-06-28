from __future__ import unicode_literals

import frappe
import warnings

from frappe.utils import get_datetime

from pymysql.times import TimeDelta
from pymysql.constants 	import ER, FIELD_TYPE
from pymysql.converters import conversions
import pymysql

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
	class ProgrammingError(pymysql.ProgrammingError): pass
	class OperationalError(pymysql.OperationalError): pass
	class InternalError(pymysql.InternalError): pass
	class SQLError(pymysql.ProgrammingError): pass
	class DataError(pymysql.DataError): pass


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

	def is_bad_field(self, e):
		return e.args[0] == ER.BAD_FIELD_ERROR

	def is_access_denied(self, e):
		return e.args[0] == ER.ACCESS_DENIED_ERROR

	def cant_drop_field_or_key(self, e):
		return e.args[0] == ER.CANT_DROP_FIELD_OR_KEY

def setup_database(force, verbose):
	frappe.local.session = frappe._dict({'user':'Administrator'})

	db_name = frappe.local.conf.db_name
	dbman = DbManager(get_root_connection())
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
	frappe.db.close()

def get_root_connection():
	import getpass
	if not frappe.local.flags.root_connection:
		root_login, root_password = frappe.flags.root_login, frappe.flags.root_password
		if root_login:
			if not root_password:
				root_password = frappe.conf.get("root_password") or None

			if not root_password:
				root_password = getpass.getpass("MySQL root password: ")
		frappe.local.flags.root_connection = frappe.database.get_db(user=root_login, password=root_password)

	return frappe.local.flags.root_connection
