from __future__ import unicode_literals

import warnings

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

class MariadbDatabase(Database):
	class ProgrammingError(psycopg2.ProgrammingError): pass
	class OperationalError(psycopg2.OperationalError): pass
	class InternalError(psycopg2.InternalError): pass
	class SQLError(psycopg2.ProgrammingError): pass
	class DataError(psycopg2.DataError): pass
	class InterfaceError(psycopg2.InterfaceError): pass

	def get_connection(self):
		warnings.filterwarnings('ignore', category=psycopg2.Warning)
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

def setup_database(force, verbose):
	subprocess.check_output(['createdb', frappe.conf.db_name])
