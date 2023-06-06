# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import datetime
import json
import random
import re
import string
import traceback
from contextlib import contextmanager, suppress
from time import time

from pypika.terms import Criterion, NullValue

import frappe
import frappe.defaults
import frappe.model.meta
from frappe import _
from frappe.database.utils import (
	DefaultOrderBy,
	EmptyQueryValues,
	FallBackDateTimeStr,
	LazyMogrify,
	Query,
	QueryValues,
	is_query_type,
)
from frappe.exceptions import DoesNotExistError, ImplicitCommitError
from frappe.model.utils.link_count import flush_local_link_count
from frappe.query_builder.functions import Count
from frappe.utils import cast as cast_fieldtype
from frappe.utils import cint, get_datetime, get_table_name, getdate, now, sbool
from frappe.utils.deprecations import deprecated, deprecation_warning

IFNULL_PATTERN = re.compile(r"ifnull\(", flags=re.IGNORECASE)
INDEX_PATTERN = re.compile(r"\s*\([^)]+\)\s*")
SINGLE_WORD_PATTERN = re.compile(r'([`"]?)(tab([A-Z]\w+))\1')
MULTI_WORD_PATTERN = re.compile(r'([`"])(tab([A-Z]\w+)( [A-Z]\w+)+)\1')


class Database:
	"""
	Open a database connection with the given parmeters, if use_default is True, use the
	login details from `conf.py`. This is called by the request handler and is accessible using
	the `db` global variable. the `sql` method is also global to run queries
	"""

	VARCHAR_LEN = 140
	MAX_COLUMN_LENGTH = 64

	OPTIONAL_COLUMNS = ["_user_tags", "_comments", "_assign", "_liked_by"]
	DEFAULT_SHORTCUTS = ["_Login", "__user", "_Full Name", "Today", "__today", "now", "Now"]
	STANDARD_VARCHAR_COLUMNS = ("name", "owner", "modified_by")
	DEFAULT_COLUMNS = ["name", "creation", "modified", "modified_by", "owner", "docstatus", "idx"]
	CHILD_TABLE_COLUMNS = ("parent", "parenttype", "parentfield")
	MAX_WRITES_PER_TRANSACTION = 200_000

	# NOTE:
	# FOR MARIADB - using no cache - as during backup, if the sequence was used in anyform,
	# it drops the cache and uses the next non cached value in setval query and
	# puts that in the backup file, which will start the counter
	# from that value when inserting any new record in the doctype.
	# By default the cache is 1000 which will mess up the sequence when
	# using the system after a restore.
	#
	# Another case could be if the cached values expire then also there is a chance of
	# the cache being skipped.
	#
	# FOR POSTGRES - The sequence cache for postgres is per connection.
	# Since we're opening and closing connections for every request this results in skipping the cache
	# to the next non-cached value hence not using cache in postgres.
	# ref: https://stackoverflow.com/questions/21356375/postgres-9-0-4-sequence-skipping-numbers
	SEQUENCE_CACHE = 0

	class InvalidColumnName(frappe.ValidationError):
		pass

	def __init__(
		self,
		host=None,
		user=None,
		password=None,
		ac_name=None,
		use_default=0,
		port=None,
	):
		self.setup_type_map()
		self.host = host or frappe.conf.db_host or "127.0.0.1"
		self.port = port or frappe.conf.db_port or ""
		self.user = user or frappe.conf.db_name
		self.db_name = frappe.conf.db_name
		self._conn = None

		if ac_name:
			self.user = ac_name or frappe.conf.db_name

		if use_default:
			self.user = frappe.conf.db_name

		self.transaction_writes = 0
		self.auto_commit_on_many_writes = 0

		self.password = password or frappe.conf.db_password
		self.value_cache = {}
		self.logger = frappe.logger("database")
		self.logger.setLevel("WARNING")
		# self.db_type: str
		# self.last_query (lazy) attribute of last sql query executed

	def setup_type_map(self):
		pass

	def connect(self):
		"""Connects to a database as set in `site_config.json`."""
		self.cur_db_name = self.user
		self._conn = self.get_connection()
		self._cursor = self._conn.cursor()
		frappe.local.rollback_observers = []

		try:
			if execution_timeout := get_query_execution_timeout():
				self.set_execution_timeout(execution_timeout)
		except Exception as e:
			self.logger.warning(f"Couldn't set execution timeout {e}")

	def set_execution_timeout(self, seconds: int):
		"""Set session speicifc timeout on exeuction of statements.
		If any statement takes more time it will be killed along with entire transaction."""
		raise NotImplementedError

	def use(self, db_name):
		"""`USE` db_name."""
		self._conn.select_db(db_name)

	def get_connection(self):
		"""Returns a Database connection object that conforms with https://peps.python.org/pep-0249/#connection-objects"""
		raise NotImplementedError

	def get_database_size(self):
		raise NotImplementedError

	def _transform_query(self, query: Query, values: QueryValues) -> tuple:
		return query, values

	def _transform_result(self, result: list[tuple]) -> list[tuple]:
		return result

	def sql(
		self,
		query: Query,
		values: QueryValues = EmptyQueryValues,
		as_dict=0,
		as_list=0,
		formatted=0,
		debug=0,
		ignore_ddl=0,
		as_utf8=0,
		auto_commit=0,
		update=None,
		explain=False,
		run=True,
		pluck=False,
	):
		"""Execute a SQL query and fetch all rows.

		:param query: SQL query.
		:param values: Tuple / List / Dict of values to be escaped and substituted in the query.
		:param as_dict: Return as a dictionary.
		:param as_list: Always return as a list.
		:param formatted: Format values like date etc.
		:param debug: Print query and `EXPLAIN` in debug log.
		:param ignore_ddl: Catch exception if table, column missing.
		:param as_utf8: Encode values as UTF 8.
		:param auto_commit: Commit after executing the query.
		:param update: Update this dict to all rows (if returned `as_dict`).
		:param run: Returns query without executing it if False.
		Examples:

		        # return customer names as dicts
		        frappe.db.sql("select name from tabCustomer", as_dict=True)

		        # return names beginning with a
		        frappe.db.sql("select name from tabCustomer where name like %s", "a%")

		        # values as dict
		        frappe.db.sql("select name from tabCustomer where name like %(name)s and owner=%(owner)s",
		                {"name": "a%", "owner":"test@example.com"})

		"""
		debug = debug or getattr(self, "debug", False)
		query = str(query)
		if not run:
			return query

		# remove whitespace / indentation from start and end of query
		query = query.strip()

		# replaces ifnull in query with coalesce
		query = IFNULL_PATTERN.sub("coalesce(", query)

		if not self._conn:
			self.connect()

		# in transaction validations
		self.check_transaction_status(query)
		self.clear_db_table_cache(query)

		if auto_commit:
			self.commit()

		if debug:
			time_start = time()

		if values == EmptyQueryValues:
			values = None
		elif not isinstance(values, (tuple, dict, list)):
			values = (values,)
		query, values = self._transform_query(query, values)

		try:
			self._cursor.execute(query, values)
		except Exception as e:
			if self.is_syntax_error(e):
				frappe.errprint(f"Syntax error in query:\n{query} {values or ''}")

			elif self.is_deadlocked(e):
				raise frappe.QueryDeadlockError(e) from e

			elif self.is_timedout(e):
				raise frappe.QueryTimeoutError(e) from e

			elif self.is_read_only_mode_error(e):
				frappe.throw(
					_(
						"Site is running in read only mode, this action can not be performed right now. Please try again later."
					),
					title=_("In Read Only Mode"),
					exc=frappe.InReadOnlyMode,
				)

			# TODO: added temporarily
			elif self.db_type == "postgres":
				traceback.print_stack()
				frappe.errprint(f"Error in query:\n{e}")
				raise

			elif isinstance(e, self.ProgrammingError):
				if frappe.conf.developer_mode:
					traceback.print_stack()
					frappe.errprint(f"Error in query:\n{query, values}")
				raise

			if not (
				ignore_ddl
				and (self.is_missing_column(e) or self.is_table_missing(e) or self.cant_drop_field_or_key(e))
			):
				raise

		if debug:
			time_end = time()
			frappe.errprint(f"Execution time: {time_end - time_start:.2f} sec")

		self.log_query(query, values, debug, explain)

		if auto_commit:
			self.commit()

		if not self._cursor.description:
			return ()

		self.last_result = self._transform_result(self._cursor.fetchall())

		if pluck:
			return [r[0] for r in self.last_result]

		if as_utf8:
			deprecation_warning("as_utf8 parameter is deprecated and will be removed in version 15.")
		if formatted:
			deprecation_warning("formatted parameter is deprecated and will be removed in version 15.")

		# scrub output if required
		if as_dict:
			ret = self.fetch_as_dict(formatted, as_utf8)
			if update:
				for r in ret:
					r.update(update)
			return ret
		elif as_list or as_utf8:
			return self.convert_to_lists(self.last_result, formatted, as_utf8)
		return self.last_result

	def _log_query(
		self,
		mogrified_query: str,
		debug: bool = False,
		explain: bool = False,
		unmogrified_query: str = "",
	) -> None:
		"""Takes the query and logs it to various interfaces according to the settings."""
		_query = None

		if frappe.conf.allow_tests and frappe.cache().get_value("flag_print_sql"):
			_query = _query or str(mogrified_query)
			print(_query)

		if debug:
			_query = _query or str(mogrified_query)
			if explain and is_query_type(_query, "select"):
				self.explain_query(_query)
			frappe.errprint(_query)

		if frappe.conf.logging == 2:
			_query = _query or str(mogrified_query)
			frappe.log(f"<<<< query\n{_query}\n>>>>")

		if unmogrified_query and is_query_type(
			unmogrified_query, ("alter", "drop", "create", "truncate", "rename")
		):
			_query = _query or str(mogrified_query)
			self.logger.warning("DDL Query made to DB:\n" + _query)

		if frappe.flags.in_migrate:
			_query = _query or str(mogrified_query)
			self.log_touched_tables(_query)

	def log_query(
		self, query: str, values: QueryValues = None, debug: bool = False, explain: bool = False
	) -> str:
		# TODO: Use mogrify until MariaDB Connector/C 1.1 is released and we can fetch something
		# like cursor._transformed_statement from the cursor object. We can also avoid setting
		# mogrified_query if we don't need to log it.
		mogrified_query = self.lazy_mogrify(query, values)
		self._log_query(mogrified_query, debug, explain, unmogrified_query=query)
		return mogrified_query

	def mogrify(self, query: Query, values: QueryValues):
		"""build the query string with values"""
		if not values:
			return query

		try:
			return self._cursor.mogrify(query, values)
		except AttributeError:
			if isinstance(values, dict):
				return query % {k: frappe.db.escape(v) if isinstance(v, str) else v for k, v in values.items()}
			elif isinstance(values, (list, tuple)):
				return query % tuple(frappe.db.escape(v) if isinstance(v, str) else v for v in values)
			return query, values

	def lazy_mogrify(self, query: Query, values: QueryValues) -> LazyMogrify:
		"""Wrap the object with str to generate mogrified query."""
		return LazyMogrify(query, values)

	def explain_query(self, query, values=None):
		"""Print `EXPLAIN` in error log."""
		frappe.errprint("--- query explain ---")
		try:
			self._cursor.execute(f"EXPLAIN {query}", values)
		except Exception as e:
			frappe.errprint(f"error in query explain: {e}")
		else:
			frappe.errprint(json.dumps(self.fetch_as_dict(), indent=1))
			frappe.errprint("--- query explain end ---")

	def sql_list(self, query, values=(), debug=False, **kwargs):
		"""Return data as list of single elements (first column).

		Example:

		        # doctypes = ["DocType", "DocField", "User", ...]
		        doctypes = frappe.db.sql_list("select name from DocType")
		"""
		return self.sql(query, values, **kwargs, debug=debug, pluck=True)

	def sql_ddl(self, query, debug=False):
		"""Commit and execute a query. DDL (Data Definition Language) queries that alter schema
		autocommit in MariaDB."""
		self.commit()
		self.sql(query, debug=debug)

	def check_transaction_status(self, query):
		"""Raises exception if more than 20,000 `INSERT`, `UPDATE` queries are
		executed in one transaction. This is to ensure that writes are always flushed otherwise this
		could cause the system to hang."""
		self.check_implicit_commit(query)

		if query and is_query_type(query, ("commit", "rollback")):
			self.transaction_writes = 0

		if query[:6].lower() in ("update", "insert", "delete"):
			self.transaction_writes += 1
			if self.transaction_writes > self.MAX_WRITES_PER_TRANSACTION:
				if self.auto_commit_on_many_writes:
					self.commit()
				else:
					msg = "<br><br>" + _("Too many changes to database in single action.") + "<br>"
					msg += _("The changes have been reverted.") + "<br>"
					raise frappe.TooManyWritesError(msg)

	def check_implicit_commit(self, query):
		if (
			self.transaction_writes
			and query
			and is_query_type(query, ("start", "alter", "drop", "create", "begin", "truncate"))
		):
			raise ImplicitCommitError("This statement can cause implicit commit")

	def fetch_as_dict(self, formatted=0, as_utf8=0) -> list[frappe._dict]:
		"""Internal. Converts results to dict."""
		result = self.last_result
		if result:
			keys = [column[0] for column in self._cursor.description]

		if not as_utf8:
			return [frappe._dict(zip(keys, row)) for row in result]

		ret = []
		for r in result:
			values = []
			for value in r:
				if as_utf8 and isinstance(value, str):
					value = value.encode("utf-8")
				values.append(value)

			ret.append(frappe._dict(zip(keys, values)))
		return ret

	@staticmethod
	def clear_db_table_cache(query):
		if query and is_query_type(query, ("drop", "create")):
			frappe.cache().delete_key("db_tables")

	@staticmethod
	def needs_formatting(result, formatted):
		"""Returns true if the first row in the result has a Date, Datetime, Long Int."""
		if result and result[0]:
			for v in result[0]:
				if isinstance(v, (datetime.date, datetime.timedelta, datetime.datetime, int)):
					return True
				if formatted and isinstance(v, (int, float)):
					return True

		return False

	def get_description(self):
		"""Returns result metadata."""
		return self._cursor.description

	@staticmethod
	def convert_to_lists(res, formatted=0, as_utf8=0):
		"""Convert tuple output to lists (internal)."""
		if not as_utf8:
			return [[value for value in row] for row in res]

		nres = []
		for r in res:
			nr = []
			for val in r:
				if as_utf8 and isinstance(val, str):
					val = val.encode("utf-8")
				nr.append(val)
			nres.append(nr)
		return nres

	def get(self, doctype, filters=None, as_dict=True, cache=False):
		"""Returns `get_value` with fieldname='*'"""
		return self.get_value(doctype, filters, "*", as_dict=as_dict, cache=cache)

	def get_value(
		self,
		doctype,
		filters=None,
		fieldname="name",
		ignore=None,
		as_dict=False,
		debug=False,
		order_by=DefaultOrderBy,
		cache=False,
		for_update=False,
		*,
		run=True,
		pluck=False,
		distinct=False,
	):
		"""Returns a document property or list of properties.

		:param doctype: DocType name.
		:param filters: Filters like `{"x":"y"}` or name of the document. `None` if Single DocType.
		:param fieldname: Column name.
		:param ignore: Don't raise exception if table, column is missing.
		:param as_dict: Return values as dict.
		:param debug: Print query in error log.
		:param order_by: Column to order by

		Example:

		        # return first customer starting with a
		        frappe.db.get_value("Customer", {"name": ("like a%")})

		        # return last login of **User** `test@example.com`
		        frappe.db.get_value("User", "test@example.com", "last_login")

		        last_login, last_ip = frappe.db.get_value("User", "test@example.com",
		                ["last_login", "last_ip"])

		        # returns default date_format
		        frappe.db.get_value("System Settings", None, "date_format")
		"""

		result = self.get_values(
			doctype,
			filters,
			fieldname,
			ignore,
			as_dict,
			debug,
			order_by,
			cache=cache,
			for_update=for_update,
			run=run,
			pluck=pluck,
			distinct=distinct,
			limit=1,
		)

		if not run:
			return result

		if not result:
			return None

		row = result[0]

		if len(row) > 1 or as_dict:
			return row
		# single field is requested, send it without wrapping in containers
		return row[0]

	def get_values(
		self,
		doctype,
		filters=None,
		fieldname="name",
		ignore=None,
		as_dict=False,
		debug=False,
		order_by=DefaultOrderBy,
		update=None,
		cache=False,
		for_update=False,
		*,
		run=True,
		pluck=False,
		distinct=False,
		limit=None,
	):
		"""Returns multiple document properties.

		:param doctype: DocType name.
		:param filters: Filters like `{"x":"y"}` or name of the document.
		:param fieldname: Column name.
		:param ignore: Don't raise exception if table, column is missing.
		:param as_dict: Return values as dict.
		:param debug: Print query in error log.
		:param order_by: Column to order by,
		:param distinct: Get Distinct results.

		Example:

		        # return first customer starting with a
		        customers = frappe.db.get_values("Customer", {"name": ("like a%")})

		        # return last login of **User** `test@example.com`
		        user = frappe.db.get_values("User", "test@example.com", "*")[0]
		"""
		out = None
		if cache and isinstance(filters, str) and (doctype, filters, fieldname) in self.value_cache:
			return self.value_cache[(doctype, filters, fieldname)]

		if distinct:
			order_by = None

		if isinstance(filters, list):
			out = self._get_value_for_many_names(
				doctype=doctype,
				names=filters,
				field=fieldname,
				order_by=order_by,
				debug=debug,
				run=run,
				pluck=pluck,
				distinct=distinct,
				limit=limit,
				as_dict=as_dict,
			)

		else:
			fields = fieldname
			if fieldname != "*":
				if isinstance(fieldname, str):
					fields = [fieldname]

			if (filters is not None) and (filters != doctype or doctype == "DocType"):
				try:
					if order_by:
						order_by = "modified" if order_by == DefaultOrderBy else order_by
					out = self._get_values_from_table(
						fields=fields,
						filters=filters,
						doctype=doctype,
						as_dict=as_dict,
						debug=debug,
						order_by=order_by,
						update=update,
						for_update=for_update,
						run=run,
						pluck=pluck,
						distinct=distinct,
						limit=limit,
					)
				except Exception as e:
					if ignore and (frappe.db.is_missing_column(e) or frappe.db.is_table_missing(e)):
						# table or column not found, return None
						out = None
					elif (not ignore) and frappe.db.is_table_missing(e):
						# table not found, look in singles
						out = self.get_values_from_single(
							fields, filters, doctype, as_dict, debug, update, run=run, distinct=distinct
						)

					else:
						raise
			else:
				out = self.get_values_from_single(
					fields, filters, doctype, as_dict, debug, update, run=run, pluck=pluck, distinct=distinct
				)

		if cache and isinstance(filters, str):
			self.value_cache[(doctype, filters, fieldname)] = out

		return out

	def get_values_from_single(
		self,
		fields,
		filters,
		doctype,
		as_dict=False,
		debug=False,
		update=None,
		*,
		run=True,
		pluck=False,
		distinct=False,
	):
		"""Get values from `tabSingles` (Single DocTypes) (internal).

		:param fields: List of fields,
		:param filters: Filters (dict).
		:param doctype: DocType name.
		"""
		if fields == "*" or isinstance(filters, dict):
			# check if single doc matches with filters
			values = self.get_singles_dict(doctype)
			if isinstance(filters, dict):
				for key, value in filters.items():
					if values.get(key) != value:
						return []

			if as_dict:
				return [values] if values else []

			if isinstance(fields, list):
				return [list(map(values.get, fields))]

		else:
			r = frappe.qb.engine.get_query(
				"Singles",
				filters={"field": ("in", tuple(fields)), "doctype": doctype},
				fields=["field", "value"],
				distinct=distinct,
			).run(pluck=pluck, debug=debug, as_dict=False)

			if not run:
				return r
			if as_dict:
				if r:
					r = frappe._dict(r)
					if update:
						r.update(update)
					return [r]
				else:
					return []
			else:
				return r and [[i[1] for i in r]] or []

	def get_singles_dict(self, doctype, debug=False, *, for_update=False, cast=False):
		"""Get Single DocType as dict.

		:param doctype: DocType of the single object whose value is requested
		:param debug: Execute query in debug mode - print to STDOUT
		:param for_update: Take `FOR UPDATE` lock on the records
		:param cast: Cast values to Python data types based on field type

		Example:

		        # Get coulmn and value of the single doctype Accounts Settings
		        account_settings = frappe.db.get_singles_dict("Accounts Settings")
		"""
		queried_result = frappe.qb.engine.get_query(
			"Singles",
			filters={"doctype": doctype},
			fields=["field", "value"],
			for_update=for_update,
		).run(debug=debug)

		if not cast:
			return frappe._dict(queried_result)

		try:
			meta = frappe.get_meta(doctype)
		except DoesNotExistError:
			return frappe._dict(queried_result)

		return_value = frappe._dict()

		for fieldname, value in queried_result:
			if df := meta.get_field(fieldname):
				casted_value = cast_fieldtype(df.fieldtype, value)
			else:
				casted_value = value
			return_value[fieldname] = casted_value

		return return_value

	@staticmethod
	def get_all(*args, **kwargs):
		return frappe.get_all(*args, **kwargs)

	@staticmethod
	def get_list(*args, **kwargs):
		return frappe.get_list(*args, **kwargs)

	def set_single_value(
		self,
		doctype: str,
		fieldname: str | dict,
		value: str | int | None = None,
		*args,
		**kwargs,
	):
		"""Set field value of Single DocType.

		:param doctype: DocType of the single object
		:param fieldname: `fieldname` of the property
		:param value: `value` of the property

		Example:

		        # Update the `deny_multiple_sessions` field in System Settings DocType.
		        company = frappe.db.set_single_value("System Settings", "deny_multiple_sessions", True)
		"""
		return self.set_value(doctype, doctype, fieldname, value, *args, **kwargs)

	def get_single_value(self, doctype, fieldname, cache=True):
		"""Get property of Single DocType. Cache locally by default

		:param doctype: DocType of the single object whose value is requested
		:param fieldname: `fieldname` of the property whose value is requested

		Example:

		        # Get the default value of the company from the Global Defaults doctype.
		        company = frappe.db.get_single_value('Global Defaults', 'default_company')
		"""

		if doctype not in self.value_cache:
			self.value_cache[doctype] = {}

		if cache and fieldname in self.value_cache[doctype]:
			return self.value_cache[doctype][fieldname]

		val = frappe.qb.engine.get_query(
			table="Singles",
			filters={"doctype": doctype, "field": fieldname},
			fields="value",
		).run()
		val = val[0][0] if val else None

		df = frappe.get_meta(doctype).get_field(fieldname)

		if not df:
			frappe.throw(
				_("Invalid field name: {0}").format(frappe.bold(fieldname)), self.InvalidColumnName
			)

		val = cast_fieldtype(df.fieldtype, val)

		self.value_cache[doctype][fieldname] = val

		return val

	def get_singles_value(self, *args, **kwargs):
		"""Alias for get_single_value"""
		return self.get_single_value(*args, **kwargs)

	def _get_values_from_table(
		self,
		fields,
		filters,
		doctype,
		as_dict,
		*,
		debug=False,
		order_by=None,
		update=None,
		for_update=False,
		run=True,
		pluck=False,
		distinct=False,
		limit=None,
	):
		field_objects = []
		query = frappe.qb.engine.get_query(
			table=doctype,
			filters=filters,
			orderby=order_by,
			for_update=for_update,
			field_objects=field_objects,
			fields=fields,
			distinct=distinct,
			limit=limit,
		)
		if fields == "*" and not isinstance(fields, (list, tuple)) and not isinstance(fields, Criterion):
			as_dict = True

		return query.run(as_dict=as_dict, debug=debug, update=update, run=run, pluck=pluck)

	def _get_value_for_many_names(
		self,
		doctype,
		names,
		field,
		order_by,
		*,
		debug=False,
		run=True,
		pluck=False,
		distinct=False,
		limit=None,
		as_dict=False,
	):
		if names := list(filter(None, names)):
			return self.get_all(
				doctype,
				fields=field,
				filters=names,
				order_by=order_by,
				pluck=pluck,
				debug=debug,
				as_list=not as_dict,
				run=run,
				distinct=distinct,
				limit_page_length=limit,
			)
		return {}

	@deprecated
	def update(self, *args, **kwargs):
		"""Update multiple values. Alias for `set_value`."""
		return self.set_value(*args, **kwargs)

	def set_value(
		self,
		dt,
		dn,
		field,
		val=None,
		modified=None,
		modified_by=None,
		update_modified=True,
		debug=False,
		for_update=True,
	):
		"""Set a single value in the database, do not call the ORM triggers
		but update the modified timestamp (unless specified not to).

		**Warning:** this function will not call Document events and should be avoided in normal cases.

		:param dt: DocType name.
		:param dn: Document name.
		:param field: Property / field name or dictionary of values to be updated
		:param value: Value to be updated.
		:param modified: Use this as the `modified` timestamp.
		:param modified_by: Set this user as `modified_by`.
		:param update_modified: default True. Set as false, if you don't want to update the timestamp.
		:param debug: Print the query in the developer / js console.
		:param for_update: [DEPRECATED] This function now performs updates in single query, locking is not required.
		"""
		is_single_doctype = not (dn and dt != dn)
		to_update = field if isinstance(field, dict) else {field: val}

		if is_single_doctype:
			deprecation_warning(
				"Calling db.set_value to set single doctype values is deprecated. This behaviour will be removed in version 15. Use db.set_single_value instead."
			)

		if update_modified:
			modified = modified or now()
			modified_by = modified_by or frappe.session.user
			to_update.update({"modified": modified, "modified_by": modified_by})

		if is_single_doctype:
			frappe.db.delete(
				"Singles", filters={"field": ("in", tuple(to_update)), "doctype": dt}, debug=debug
			)

			singles_data = ((dt, key, sbool(value)) for key, value in to_update.items())
			query = (
				frappe.qb.into("Singles").columns("doctype", "field", "value").insert(*singles_data)
			).run(debug=debug)
			frappe.clear_document_cache(dt, dt)

		else:
			query = frappe.qb.engine.build_conditions(table=dt, filters=dn, update=True)

			if isinstance(dn, str):
				frappe.clear_document_cache(dt, dn)
			else:
				# TODO: Fix this; doesn't work rn - gavin@frappe.io
				# frappe.cache().hdel_keys(dt, "document_cache")
				# Workaround: clear all document caches
				frappe.cache().delete_value("document_cache")

			for column, value in to_update.items():
				query = query.set(column, value)

			query.run(debug=debug)

		if dt in self.value_cache:
			del self.value_cache[dt]

	@staticmethod
	@deprecated
	def set(doc, field, val):
		"""Set value in document. **Avoid**"""
		doc.db_set(field, val)

	@deprecated
	def touch(self, doctype, docname):
		"""Update the modified timestamp of this document."""
		modified = now()
		DocType = frappe.qb.DocType(doctype)
		frappe.qb.update(DocType).set(DocType.modified, modified).where(DocType.name == docname).run()
		return modified

	@staticmethod
	def set_temp(value):
		"""Set a temperory value and return a key."""
		key = frappe.generate_hash()
		frappe.cache().hset("temp", key, value)
		return key

	@staticmethod
	def get_temp(key):
		"""Return the temperory value and delete it."""
		return frappe.cache().hget("temp", key)

	def set_global(self, key, val, user="__global"):
		"""Save a global key value. Global values will be automatically set if they match fieldname."""
		self.set_default(key, val, user)

	def get_global(self, key, user="__global"):
		"""Returns a global key value."""
		return self.get_default(key, user)

	def get_default(self, key, parent="__default"):
		"""Returns default value as a list if multiple or single"""
		d = self.get_defaults(key, parent)
		return isinstance(d, list) and d[0] or d

	@staticmethod
	def set_default(key, val, parent="__default", parenttype=None):
		"""Sets a global / user default value."""
		frappe.defaults.set_default(key, val, parent, parenttype)

	@staticmethod
	def add_default(key, val, parent="__default", parenttype=None):
		"""Append a default value for a key, there can be multiple default values for a particular key."""
		frappe.defaults.add_default(key, val, parent, parenttype)

	@staticmethod
	def get_defaults(key=None, parent="__default"):
		"""Get all defaults"""
		defaults = frappe.defaults.get_defaults_for(parent)
		if not key:
			return defaults

		if key in defaults:
			return defaults[key]

		return defaults.get(frappe.scrub(key))

	def begin(self, *, read_only=False):
		read_only = read_only or frappe.flags.read_only
		mode = "READ ONLY" if read_only else ""
		self.sql(f"START TRANSACTION {mode}")

	def commit(self):
		"""Commit current transaction. Calls SQL `COMMIT`."""
		for method in frappe.local.before_commit:
			frappe.call(method[0], *(method[1] or []), **(method[2] or {}))

		self.sql("commit")
		self.begin()  # explicitly start a new transaction

		frappe.local.rollback_observers = []
		self.flush_realtime_log()
		enqueue_jobs_after_commit()
		flush_local_link_count()

	def add_before_commit(self, method, args=None, kwargs=None):
		frappe.local.before_commit.append([method, args, kwargs])

	@staticmethod
	def flush_realtime_log():
		for args in frappe.local.realtime_log:
			frappe.realtime.emit_via_redis(*args)

		frappe.local.realtime_log = []

	def savepoint(self, save_point):
		"""Savepoints work as a nested transaction.

		Changes can be undone to a save point by doing frappe.db.rollback(save_point)

		Note: rollback watchers can not work with save points.
		        so only changes to database are undone when rolling back to a savepoint.
		        Avoid using savepoints when writing to filesystem."""
		self.sql(f"savepoint {save_point}")

	def release_savepoint(self, save_point):
		self.sql(f"release savepoint {save_point}")

	def rollback(self, *, save_point=None):
		"""`ROLLBACK` current transaction. Optionally rollback to a known save_point."""
		if save_point:
			self.sql(f"rollback to savepoint {save_point}")
		else:
			self.sql("rollback")
			self.begin()
			for obj in dict.fromkeys(frappe.local.rollback_observers):
				if hasattr(obj, "on_rollback"):
					obj.on_rollback()
			frappe.local.rollback_observers = []

			frappe.local.realtime_log = []
			frappe.flags.enqueue_after_commit = []

	def field_exists(self, dt, fn):
		"""Return true of field exists."""
		return self.exists("DocField", {"fieldname": fn, "parent": dt})

	def table_exists(self, doctype, cached=True):
		"""Returns True if table for given doctype exists."""
		return f"tab{doctype}" in self.get_tables(cached=cached)

	def has_table(self, doctype):
		return self.table_exists(doctype)

	def get_tables(self, cached=True):
		raise NotImplementedError

	def a_row_exists(self, doctype):
		"""Returns True if atleast one row exists."""
		return frappe.get_all(doctype, limit=1, order_by=None, as_list=True)

	def exists(self, dt, dn=None, cache=False):
		"""Return the document name of a matching document, or None.

		Note: `cache` only works if `dt` and `dn` are of type `str`.

		## Examples

		Pass doctype and docname (only in this case we can cache the result)

		```
		exists("User", "jane@example.org", cache=True)
		```

		Pass a dict of filters including the `"doctype"` key:

		```
		exists({"doctype": "User", "full_name": "Jane Doe"})
		```

		Pass the doctype and a dict of filters:

		```
		exists("User", {"full_name": "Jane Doe"})
		```
		"""
		if dt != "DocType" and dt == dn:
			# single always exists (!)
			return dn

		if isinstance(dt, dict):
			dt = dt.copy()  # don't modify the original dict
			dt, dn = dt.pop("doctype"), dt

		return self.get_value(dt, dn, ignore=True, cache=cache)

	def count(self, dt, filters=None, debug=False, cache=False, distinct: bool = True):
		"""Returns `COUNT(*)` for given DocType and filters."""
		if cache and not filters:
			cache_count = frappe.cache().get_value(f"doctype:count:{dt}")
			if cache_count is not None:
				return cache_count
		query = frappe.qb.engine.get_query(
			table=dt, filters=filters, fields=Count("*"), distinct=distinct
		)
		count = query.run(debug=debug)[0][0]
		if not filters and cache:
			frappe.cache().set_value(f"doctype:count:{dt}", count, expires_in_sec=86400)
		return count

	@staticmethod
	def format_date(date):
		return getdate(date).strftime("%Y-%m-%d")

	@staticmethod
	def format_datetime(datetime):
		if not datetime:
			return FallBackDateTimeStr

		return get_datetime(datetime).strftime("%Y-%m-%d %H:%M:%S.%f")

	def get_creation_count(self, doctype, minutes):
		"""Get count of records created in the last x minutes"""
		from dateutil.relativedelta import relativedelta

		from frappe.utils import now_datetime

		Table = frappe.qb.DocType(doctype)

		return (
			frappe.qb.from_(Table)
			.select(Count(Table.name))
			.where(Table.creation >= now_datetime() - relativedelta(minutes=minutes))
			.run()[0][0]
		)

	def get_db_table_columns(self, table) -> list[str]:
		"""Returns list of column names from given table."""
		columns = frappe.cache().hget("table_columns", table)
		if columns is None:
			information_schema = frappe.qb.Schema("information_schema")

			columns = (
				frappe.qb.from_(information_schema.columns)
				.select(information_schema.columns.column_name)
				.where(information_schema.columns.table_name == table)
				.run(pluck=True)
			)

			if columns:
				frappe.cache().hset("table_columns", table, columns)

		return columns

	def get_table_columns(self, doctype):
		"""Returns list of column names from given doctype."""
		columns = self.get_db_table_columns("tab" + doctype)
		if not columns:
			raise self.TableMissingError("DocType", doctype)
		return columns

	def has_column(self, doctype, column):
		"""Returns True if column exists in database."""
		return column in self.get_table_columns(doctype)

	def get_column_type(self, doctype, column):
		"""Returns column type from database."""
		information_schema = frappe.qb.Schema("information_schema")
		table = get_table_name(doctype)

		return (
			frappe.qb.from_(information_schema.columns)
			.select(information_schema.columns.column_type)
			.where(
				(information_schema.columns.table_name == table)
				& (information_schema.columns.column_name == column)
			)
			.run(pluck=True)[0]
		)

	def has_index(self, table_name, index_name):
		raise NotImplementedError

	def add_index(self, doctype, fields, index_name=None):
		raise NotImplementedError

	def add_unique(self, doctype, fields, constraint_name=None):
		raise NotImplementedError

	@staticmethod
	def get_index_name(fields):
		index_name = "_".join(fields) + "_index"
		# remove index length if present e.g. (10) from index name
		return INDEX_PATTERN.sub(r"", index_name)

	def get_system_setting(self, key):
		return frappe.get_system_settings(key)

	def close(self):
		"""Close database connection."""
		if self._conn:
			self._conn.close()
			self._cursor = None
			self._conn = None

	@staticmethod
	def escape(s, percent=True):
		"""Excape quotes and percent in given string."""
		# implemented in specific class
		raise NotImplementedError

	@staticmethod
	def is_column_missing(e):
		return frappe.db.is_missing_column(e)

	def get_descendants(self, doctype, name):
		"""Return descendants of the group node in tree"""
		from frappe.utils.nestedset import get_descendants_of

		try:
			return get_descendants_of(doctype, name, ignore_permissions=True)
		except Exception:
			# Can only happen if document doesn't exists - kept for backward compatibility
			return []

	def is_missing_table_or_column(self, e):
		return self.is_missing_column(e) or self.is_table_missing(e)

	def multisql(self, sql_dict, values=(), **kwargs):
		current_dialect = self.db_type or "mariadb"
		query = sql_dict.get(current_dialect)
		return self.sql(query, values, **kwargs)

	def delete(self, doctype: str, filters: dict | list = None, debug=False, **kwargs):
		"""Delete rows from a table in site which match the passed filters. This
		does trigger DocType hooks. Simply runs a DELETE query in the database.

		Doctype name can be passed directly, it will be pre-pended with `tab`.
		"""
		filters = filters or kwargs.get("conditions")
		query = frappe.qb.engine.build_conditions(table=doctype, filters=filters).delete()
		if "debug" not in kwargs:
			kwargs["debug"] = debug
		return query.run(**kwargs)

	def truncate(self, doctype: str):
		"""Truncate a table in the database. This runs a DDL command `TRUNCATE TABLE`.
		This cannot be rolled back.

		Doctype name can be passed directly, it will be pre-pended with `tab`.
		"""
		return self.sql_ddl(f"truncate `{get_table_name(doctype)}`")

	@deprecated
	def clear_table(self, doctype):
		return self.truncate(doctype)

	def get_last_created(self, doctype):
		last_record = self.get_all(doctype, ("creation"), limit=1, order_by="creation desc")
		if last_record:
			return get_datetime(last_record[0].creation)
		else:
			return None

	def log_touched_tables(self, query):
		if is_query_type(query, ("insert", "delete", "update", "alter", "drop", "rename")):
			# single_word_regex is designed to match following patterns
			# `tabXxx`, tabXxx and "tabXxx"

			# multi_word_regex is designed to match following patterns
			# `tabXxx Xxx` and "tabXxx Xxx"

			# ([`"]?) Captures " or ` at the begining of the table name (if provided)
			# \1 matches the first captured group (quote character) at the end of the table name
			# multi word table name must have surrounding quotes.

			# (tab([A-Z]\w+)( [A-Z]\w+)*) Captures table names that start with "tab"
			# and are continued with multiple words that start with a captital letter
			# e.g. 'tabXxx' or 'tabXxx Xxx' or 'tabXxx Xxx Xxx' and so on

			tables = []
			for regex in (SINGLE_WORD_PATTERN, MULTI_WORD_PATTERN):
				tables += [groups[1] for groups in regex.findall(query)]

			if frappe.flags.touched_tables is None:
				frappe.flags.touched_tables = set()
			frappe.flags.touched_tables.update(tables)

	def bulk_insert(self, doctype, fields, values, ignore_duplicates=False, *, chunk_size=10_000):
		"""
		Insert multiple records at a time

		:param doctype: Doctype name
		:param fields: list of fields
		:params values: list of list of values
		"""
		values = list(values)
		table = frappe.qb.DocType(doctype)

		for start_index in range(0, len(values), chunk_size):
			query = frappe.qb.into(table)
			if ignore_duplicates:
				# Pypika does not have same api for ignoring duplicates
				if self.db_type == "mariadb":
					query = query.ignore()
				elif self.db_type == "postgres":
					query = query.on_conflict().do_nothing()

			values_to_insert = values[start_index : start_index + chunk_size]
			query.columns(fields).insert(*values_to_insert).run()

	def create_sequence(self, *args, **kwargs):
		from frappe.database.sequence import create_sequence

		return create_sequence(*args, **kwargs)

	def set_next_sequence_val(self, *args, **kwargs):
		from frappe.database.sequence import set_next_val

		set_next_val(*args, **kwargs)

	def get_next_sequence_val(self, *args, **kwargs):
		from frappe.database.sequence import get_next_val

		return get_next_val(*args, **kwargs)


def enqueue_jobs_after_commit():
	from frappe.utils.background_jobs import (
		RQ_JOB_FAILURE_TTL,
		RQ_RESULTS_TTL,
		execute_job,
		get_queue,
	)

	if frappe.flags.enqueue_after_commit and len(frappe.flags.enqueue_after_commit) > 0:
		for job in frappe.flags.enqueue_after_commit:
			q = get_queue(job.get("queue"), is_async=job.get("is_async"))
			q.enqueue_call(
				execute_job,
				timeout=job.get("timeout"),
				kwargs=job.get("queue_args"),
				failure_ttl=frappe.conf.get("rq_job_failure_ttl") or RQ_JOB_FAILURE_TTL,
				result_ttl=frappe.conf.get("rq_results_ttl") or RQ_RESULTS_TTL,
				job_id=job.get("job_id"),
			)
		frappe.flags.enqueue_after_commit = []


@contextmanager
def savepoint(catch: type | tuple[type, ...] = Exception):
	"""Wrapper for wrapping blocks of DB operations in a savepoint.

	as contextmanager:

	for doc in docs:
	        with savepoint(catch=DuplicateError):
	                doc.insert()

	as decorator (wraps FULL function call):

	@savepoint(catch=DuplicateError)
	def process_doc(doc):
	        doc.insert()
	"""
	try:
		savepoint = "".join(random.sample(string.ascii_lowercase, 10))
		frappe.db.savepoint(savepoint)
		yield  # control back to calling function
	except catch:
		frappe.db.rollback(save_point=savepoint)
	else:
		frappe.db.release_savepoint(savepoint)


def get_query_execution_timeout() -> int:
	"""Get execution timeout based on current timeout in different contexts.

	    HTTP requests: HTTP timeout or a default (300)
	    Background jobs: Job timeout
	Console/Commands: No timeout = 0.

	    Note: Timeout adds 1.5x as "safety factor"
	"""
	from rq import get_current_job

	if not frappe.conf.get("enable_db_statement_timeout"):
		return 0

	# Zero means no timeout, which is the default value in db.
	timeout = 0
	with suppress(Exception):
		if getattr(frappe.local, "request", None):
			timeout = frappe.conf.http_timeout or 300
		elif job := get_current_job():
			timeout = job.timeout

	return int(cint(timeout) * 1.5)
