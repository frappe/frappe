# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import itertools
import json
import random
import re
import string
import traceback
import warnings
from collections.abc import Hashable, Iterable, Sequence
from contextlib import contextmanager, suppress
from time import time
from typing import TYPE_CHECKING, Any

from pypika.dialects import MySQLQueryBuilder, PostgreSQLQueryBuilder

import frappe
import frappe.defaults
from frappe import _
from frappe.database.utils import (
	DefaultOrderBy,
	EmptyQueryValues,
	FallBackDateTimeStr,
	FilterValue,
	LazyMogrify,
	Query,
	QueryValues,
	convert_to_value,
	is_query_type,
)
from frappe.exceptions import DoesNotExistError, ImplicitCommitError
from frappe.monitor import get_trace_id
from frappe.query_builder.functions import Count
from frappe.utils import CallbackManager, cint, get_datetime, get_table_name, getdate, now, sbool
from frappe.utils import cast as cast_fieldtype

if TYPE_CHECKING:
	from psycopg2 import connection as PostgresConnection
	from psycopg2 import cursor as PostgresCursor
	from pymysql.connections import Connection as MariadbConnection
	from pymysql.cursors import Cursor as MariadbCursor

IFNULL_PATTERN = re.compile(r"ifnull\(", flags=re.IGNORECASE)
INDEX_PATTERN = re.compile(r"\s*\([^)]+\)\s*")
SINGLE_WORD_PATTERN = re.compile(r'([`"]?)(tab([A-Z]\w+))\1')
MULTI_WORD_PATTERN = re.compile(r'([`"])(tab([A-Z]\w+)( [A-Z]\w+)+)\1')

SQL_ITERATOR_BATCH_SIZE = 100


TRANSACTION_DISABLED_MSG = """Commit/rollback are disabled during certain events. This command will
be ignored. Commit/Rollback from here WILL CAUSE very hard to debug problems with atomicity and
concurrent data update bugs."""


class Database:
	"""
	Open a database connection with the given parmeters, if use_default is True, use the
	login details from `conf.py`. This is called by the request handler and is accessible using
	the `db` global variable. the `sql` method is also global to run queries
	"""

	VARCHAR_LEN = 140
	MAX_COLUMN_LENGTH = 64

	OPTIONAL_COLUMNS = ("_user_tags", "_comments", "_assign", "_liked_by")
	DEFAULT_SHORTCUTS = ("_Login", "__user", "_Full Name", "Today", "__today", "now", "Now")
	STANDARD_VARCHAR_COLUMNS = ("name", "owner", "modified_by")
	DEFAULT_COLUMNS = ("name", "creation", "modified", "modified_by", "owner", "docstatus", "idx")
	CHILD_TABLE_COLUMNS = ("parent", "parenttype", "parentfield")
	MAX_WRITES_PER_TRANSACTION = 200_000

	class InvalidColumnName(frappe.ValidationError):
		pass

	def __init__(
		self,
		socket=None,
		host=None,
		user=None,
		password=None,
		port=None,
		cur_db_name=None,
	):
		self.setup_type_map()
		self.socket = socket
		self.host = host
		self.port = port
		self.user = user
		self.password = password
		self.cur_db_name = cur_db_name
		self._conn = None

		self.transaction_writes = 0
		self.auto_commit_on_many_writes = 0

		self.value_cache = {}
		self.logger = frappe.logger("database")
		self.logger.setLevel("WARNING")

		self.before_commit = CallbackManager()
		self.after_commit = CallbackManager()
		self.before_rollback = CallbackManager()
		self.after_rollback = CallbackManager()

		# Setting this to true will disable full rollback and commit
		# You can still use savepoint with partial rollback.
		self._disable_transaction_control = 0

		# self.db_type: str
		# self.last_query (lazy) attribute of last sql query executed

	def setup_type_map(self):
		pass

	def connect(self):
		"""Connects to a database as set in `site_config.json`."""
		self._conn: "MariadbConnection" | "PostgresConnection" = self.get_connection()
		self._cursor: "MariadbCursor" | "PostgresCursor" = self._conn.cursor()

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
		self.cur_db_name = db_name

	def get_connection(self):
		"""Return a Database connection object that conforms with https://peps.python.org/pep-0249/#connection-objects."""
		raise NotImplementedError

	def get_database_size(self):
		raise NotImplementedError

	def _transform_query(self, query: Query, values: QueryValues) -> tuple:
		return query, values

	def _transform_result(self, result: list[tuple] | tuple[tuple]) -> tuple[tuple]:
		return result

	def _clean_up(self):
		pass

	def sql(
		self,
		query: Query,
		values: QueryValues = EmptyQueryValues,
		*,
		as_dict=0,
		as_list=0,
		debug=0,
		ignore_ddl=0,
		auto_commit=0,
		update=None,
		explain=False,
		run=True,
		pluck=False,
		as_iterator=False,
	):
		"""Execute a SQL query and fetch all rows.

		:param query: SQL query.
		:param values: Tuple / List / Dict of values to be escaped and substituted in the query.
		:param as_dict: Return as a dictionary.
		:param as_list: Always return as a list.
		:param debug: Print query and `EXPLAIN` in debug log.
		:param ignore_ddl: Catch exception if table, column missing.
		:param auto_commit: Commit after executing the query.
		:param update: Update this dict to all rows (if returned `as_dict`).
		:param run: Return query without executing it if False.
		:param pluck: Get the plucked field only.
		:param explain: Print `EXPLAIN` in error log.
		:param as_iterator: Returns iterator over results instead of fetching all results at once.
		        This should be used with unbuffered cursor as default cursors used by pymysql and postgres
		        buffer the results internally. See `Database.unbuffered_cursor`.
		Examples:

		        # return customer names as dicts
		        frappe.db.sql("select name from tabCustomer", as_dict=True)

		        # return names beginning with a
		        frappe.db.sql("select name from tabCustomer where name like %s", "a%")

		        # values as dict
		        frappe.db.sql("select name from tabCustomer where name like %(name)s and owner=%(owner)s",
		                {"name": "a%", "owner":"test@example.com"})

		"""
		if isinstance(query, MySQLQueryBuilder | PostgreSQLQueryBuilder):
			frappe.log("Use run method to execute SQL queries generated by Query Builder")

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
		elif not isinstance(values, tuple | dict | list):
			values = (values,)

		query, values = self._transform_query(query, values)

		if trace_id := get_trace_id():
			query += f" /* FRAPPE_TRACE_ID: {trace_id} */"

		try:
			self._cursor.execute(query, values)
		except Exception as e:
			if self.is_syntax_error(e):
				frappe.log(f"Syntax error in query:\n{query} {values or ''}")

			elif self.is_deadlocked(e):
				raise frappe.QueryDeadlockError(e) from e

			elif self.is_timedout(e):
				raise frappe.QueryTimeoutError(e) from e

			elif self.is_read_only_mode_error(e):
				frappe.throw(
					_(
						"Site is running in read only mode for maintenance or site update, this action can not be performed right now. Please try again later."
					),
					title=_("In Read Only Mode"),
					exc=frappe.InReadOnlyMode,
				)

			# TODO: added temporarily
			elif self.db_type == "postgres":
				traceback.print_stack()
				frappe.log(f"Error in query:\n{e}")
				raise

			elif isinstance(e, self.ProgrammingError):
				if frappe.conf.developer_mode:
					traceback.print_stack()
					frappe.log(f"Error in query:\n{query, values}")
				raise

			if not (
				ignore_ddl
				and (self.is_missing_column(e) or self.is_table_missing(e) or self.cant_drop_field_or_key(e))
			):
				raise

		if debug:
			time_end = time()
			frappe.log(f"Execution time: {time_end - time_start:.2f} sec")

		self.log_query(query, values, debug, explain)

		if auto_commit:
			self.commit()

		if not self._cursor.description:
			return ()

		if as_iterator:
			return self._return_as_iterator(pluck=pluck, as_dict=as_dict, as_list=as_list, update=update)

		last_result = self._transform_result(self._cursor.fetchall())
		if pluck:
			last_result = [r[0] for r in last_result]
			self._clean_up()
			return last_result

		# scrub output if required
		if as_dict:
			last_result = self.fetch_as_dict(last_result)
			if update:
				for r in last_result:
					r.update(update)

		elif as_list:
			last_result = self.convert_to_lists(last_result)

		self._clean_up()
		return last_result

	def _return_as_iterator(self, *, pluck, as_dict, as_list, update):
		while result := self._transform_result(self._cursor.fetchmany(SQL_ITERATOR_BATCH_SIZE)):
			if pluck:
				for row in result:
					yield row[0]

			elif as_dict:
				keys = [column[0] for column in self._cursor.description]
				for row in result:
					row = frappe._dict(zip(keys, row, strict=False))
					if update:
						row.update(update)
					yield row

			elif as_list:
				for row in result:
					yield list(row)
			else:
				frappe.throw(_("`as_iterator` only works with `as_list=True` or `as_dict=True`"))

		self._clean_up()

	def _log_query(
		self,
		mogrified_query: str,
		debug: bool = False,
		explain: bool = False,
		unmogrified_query: str = "",
	) -> None:
		"""Takes the query and logs it to various interfaces according to the settings."""
		_query = None

		if frappe.conf.allow_tests and frappe.cache.get_value("flag_print_sql"):
			_query = _query or str(mogrified_query)
			print(_query)

		if debug:
			_query = _query or str(mogrified_query)
			if explain and is_query_type(_query, "select"):
				self.explain_query(_query)
			frappe.log(_query)

		if frappe.conf.logging == 2:
			_query = _query or str(mogrified_query)
			frappe.log(f"#### query\n{_query}\n####")

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
				return query % {
					k: frappe.db.escape(v) if isinstance(v, str) else v for k, v in values.items()
				}
			elif isinstance(values, list | tuple):
				return query % tuple(frappe.db.escape(v) if isinstance(v, str) else v for v in values)
			return query, values

	def lazy_mogrify(self, query: Query, values: QueryValues) -> LazyMogrify:
		"""Wrap the object with str to generate mogrified query."""
		return LazyMogrify(query, values)

	def explain_query(self, query, values=EmptyQueryValues):
		"""Print `EXPLAIN` in error log."""
		frappe.log("--- query explain ---")
		try:
			results = self.sql(f"EXPLAIN {query}", values, as_dict=1)
		except Exception as e:
			frappe.log(f"error in query explain: {e}")
		else:
			frappe.log(json.dumps(results, indent=1))
			frappe.log("--- query explain end ---")

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
		transaction_control = self._disable_transaction_control
		self._disable_transaction_control = 0
		self.commit()
		self.sql(query, debug=debug)
		self._disable_transaction_control = transaction_control

	def check_transaction_status(self, query: str):
		"""Raises exception if more than 200,000 `INSERT`, `UPDATE` queries are
		executed in one transaction. This is to ensure that writes are always flushed otherwise this
		could cause the system to hang."""
		self.check_implicit_commit(query)

		if query and is_query_type(query, ("commit", "rollback")):
			self.transaction_writes = 0

		if query.lstrip()[:6].lower() in ("update", "insert", "delete"):
			self.transaction_writes += 1
			if self.transaction_writes > self.MAX_WRITES_PER_TRANSACTION:
				if self.auto_commit_on_many_writes:
					self.commit()
				else:
					msg = "<br><br>" + _("Too many changes to database in single action.") + "<br>"
					msg += _("The changes have been reverted.") + "<br>"
					raise frappe.TooManyWritesError(msg)

	def check_implicit_commit(self, query: str):
		if (
			self.transaction_writes
			and query
			and is_query_type(query, ("start", "alter", "drop", "create", "begin", "truncate"))
		):
			raise ImplicitCommitError("This statement can cause implicit commit", query)

	def fetch_as_dict(self, result) -> list[frappe._dict]:
		"""Internal. Convert results to dict."""
		if result:
			keys = [column[0] for column in self._cursor.description]

		return [frappe._dict(zip(keys, row, strict=False)) for row in result]

	@staticmethod
	def clear_db_table_cache(query):
		if query and is_query_type(query, ("drop", "create")):
			frappe.cache.delete_key("db_tables")

	def get_description(self):
		"""Return result metadata."""
		return self._cursor.description

	@staticmethod
	def convert_to_lists(res):
		"""Convert tuple output to lists (internal)."""
		return [[value for value in row] for row in res]

	def get(self, doctype, filters=None, as_dict=True, cache=False):
		"""Return `get_value` with fieldname='*'."""
		return self.get_value(doctype, filters, "*", as_dict=as_dict, cache=cache)

	def get_value(
		self,
		doctype: str,
		filters: FilterValue | dict | list | None = None,
		fieldname: str | list[str] = "name",
		ignore: bool = False,
		as_dict: bool = False,
		debug: bool = False,
		order_by: str = DefaultOrderBy,
		cache: bool = False,
		for_update: bool = False,
		*,
		run: bool = True,
		pluck: bool = False,
		distinct: bool = False,
		skip_locked: bool = False,
		wait: bool = True,
	):
		"""Return a document property or list of properties.

		:param doctype: DocType name.
		:param filters: Filters like `{"x":"y"}` or name of the document. `None` if Single DocType.
		:param fieldname: Column name.
		:param ignore: Don't raise exception if table, column is missing.
		:param as_dict: Return values as dict.
		:param debug: Print query in error log.
		:param order_by: Column to order by
		:param cache: Use cached results fetched during current job/request
		:param pluck: pluck first column instead of returning as nested list or dict.
		:param for_update: All the affected/read rows will be locked.
		:param skip_locked: Skip selecting currently locked rows.
		:param wait: Wait for aquiring lock

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
			skip_locked=skip_locked,
			wait=wait,
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
		doctype: str,
		filters: FilterValue | dict | list | None = None,
		fieldname: str | list[str] = "name",
		ignore: bool = False,
		as_dict: bool = False,
		debug: bool = False,
		order_by: str = DefaultOrderBy,
		update: dict | None = None,
		cache: bool = False,
		for_update: bool = False,
		*,
		run: bool = True,
		pluck: bool = False,
		distinct: bool = False,
		limit: int | None = None,
		skip_locked: bool = False,
		wait: bool = True,
	):
		"""Return multiple document properties.

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
		cache_key = None
		if cache and isinstance(filters, Hashable):
			cache_key = (doctype, filters, fieldname)
			if cache_key in self.value_cache:
				return self.value_cache[cache_key]

		if distinct:
			order_by = None

		if isinstance(filters, list):
			if filters := list(f for f in filters if f is not None):
				out = frappe.qb.get_query(
					table=doctype,
					fields=fieldname,
					filters=filters,
					order_by=order_by,
					distinct=distinct,
					limit=limit,
					validate_filters=True,
					for_update=for_update,
					skip_locked=skip_locked,
					wait=True,
				).run(debug=debug, run=run, as_dict=as_dict, pluck=pluck)
			else:
				out = {}
		else:
			if (filters is not None) and (filters != doctype or doctype == "DocType"):
				try:
					if order_by:
						order_by = "creation" if order_by == DefaultOrderBy else order_by

					query = frappe.qb.get_query(
						table=doctype,
						filters=filters,
						order_by=order_by,
						for_update=for_update,
						skip_locked=skip_locked,
						wait=wait,
						fields=fieldname,
						distinct=distinct,
						limit=limit,
						validate_filters=True,
					)
					if isinstance(fieldname, str) and fieldname == "*":
						as_dict = True
					out = query.run(as_dict=as_dict, debug=debug, update=update, run=run, pluck=pluck)

				except Exception as e:
					if ignore and (
						frappe.db.is_missing_column(e)
						or frappe.db.is_table_missing(e)
						or str(e).startswith("Invalid DocType")
					):
						out = None
					elif (not ignore) and frappe.db.is_table_missing(e):
						# table not found, look in singles
						fields = (
							[fieldname] if (isinstance(fieldname, str) and fieldname != "*") else fieldname
						)
						out = self.get_values_from_single(
							fields,
							filters,
							doctype,
							as_dict,
							debug,
							update,
							run=run,
							distinct=distinct,
						)

					else:
						raise
			else:
				fields = [fieldname] if (isinstance(fieldname, str) and fieldname != "*") else fieldname
				out = self.get_values_from_single(
					fields,
					filters,
					doctype,
					as_dict,
					debug,
					update,
					run=run,
					pluck=pluck,
					distinct=distinct,
				)

		if cache and cache_key:
			self.value_cache[cache_key] = out

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
			r = frappe.qb.get_query(
				"Singles",
				filters={"field": ("in", tuple(fields)), "doctype": doctype},
				fields=["field", "value"],
				distinct=distinct,
			).run(pluck=pluck, debug=debug, as_dict=False)

			if not run:
				return r

			if not r:
				return []

			r = frappe._dict(r)
			if update:
				r.update(update)

			if not as_dict:
				return [[r.get(field) for field in fields]]

			return [r]

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
		queried_result = frappe.qb.get_query(
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

	@staticmethod
	def _get_update_dict(
		fieldname: str | dict, value: Any, *, modified: str, modified_by: str, update_modified: bool
	) -> dict[str, Any]:
		"""Create update dict that represents column-values to be updated."""
		update_dict = fieldname if isinstance(fieldname, dict) else {fieldname: value}

		if update_modified:
			modified = modified or now()
			modified_by = modified_by or frappe.session.user
			update_dict.update({"modified": modified, "modified_by": modified_by})

		return update_dict

	def set_single_value(
		self,
		doctype: str,
		fieldname: str | dict,
		value: str | int | None = None,
		*,
		modified=None,
		modified_by=None,
		update_modified=True,
		debug=False,
	):
		"""Set field value of Single DocType.

		:param doctype: DocType of the single object
		:param fieldname: `fieldname` of the property
		:param value: `value` of the property

		Example:

		        # Update the `deny_multiple_sessions` field in System Settings DocType.
		        frappe.db.set_single_value("System Settings", "deny_multiple_sessions", True)
		"""

		to_update = self._get_update_dict(
			fieldname, value, modified=modified, modified_by=modified_by, update_modified=update_modified
		)

		frappe.db.delete(
			"Singles", filters={"field": ("in", tuple(to_update)), "doctype": doctype}, debug=debug
		)

		singles_data = ((doctype, key, sbool(value)) for key, value in to_update.items())
		frappe.qb.into("Singles").columns("doctype", "field", "value").insert(*singles_data).run(debug=debug)
		frappe.clear_document_cache(doctype, doctype)

		if doctype in self.value_cache:
			del self.value_cache[doctype]

	def get_single_value(self, doctype: str, fieldname: str, cache: bool = True):
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

		val = frappe.qb.get_query(
			table="Singles",
			filters={"doctype": doctype, "field": fieldname},
			fields="value",
		).run()
		val = val[0][0] if val else None

		df = frappe.get_meta(doctype).get_field(fieldname)

		if not df:
			frappe.throw(
				_("Field {0} does not exist on {1}").format(
					frappe.bold(fieldname), frappe.bold(doctype), self.InvalidColumnName
				)
			)

		val = cast_fieldtype(df.fieldtype, val)

		self.value_cache[doctype][fieldname] = val

		return val

	def get_singles_value(self, *args, **kwargs):
		"""Alias for get_single_value"""
		return self.get_single_value(*args, **kwargs)

	def set_value(
		self,
		dt: str,
		dn: FilterValue | dict,
		field: str,
		val=None,
		modified=None,
		modified_by=None,
		update_modified=True,
		debug=False,
	):
		"""Set a single value in the database, do not call the ORM triggers
		but update the modified timestamp (unless specified not to).

		**Warning:** this function will not call Document events and should be avoided in normal cases.

		:param dt: DocType name.
		:param dn: Document name for updating single record or filters for updating many records.
		:param field: Property / field name or dictionary of values to be updated
		:param value: Value to be updated.
		:param modified: Use this as the `modified` timestamp.
		:param modified_by: Set this user as `modified_by`.
		:param update_modified: default True. Set as false, if you don't want to update the timestamp.
		:param debug: Print the query in the developer / js console.
		"""
		from frappe.model.utils import is_single_doctype

		if dn is None or dt == dn:
			if not is_single_doctype(dt):
				return
			from frappe.deprecation_dumpster import deprecation_warning

			deprecation_warning(
				"unknown",
				"v17",
				"Calling db.set_value on single doctype is deprecated. This behaviour will be removed in future. Use db.set_single_value instead.",
			)
			self.set_single_value(
				doctype=dt,
				fieldname=field,
				value=val,
				debug=debug,
				update_modified=update_modified,
				modified=modified,
				modified_by=modified_by,
			)
			return

		to_update = self._get_update_dict(
			field, val, modified=modified, modified_by=modified_by, update_modified=update_modified
		)

		query = frappe.qb.get_query(
			table=dt,
			filters=dn,
			update=True,
			validate_filters=True,
		)

		if isinstance(dn, FilterValue):
			frappe.clear_document_cache(dt, convert_to_value(dn))
		else:
			# No way to guess which documents are modified, clear all of them
			frappe.clear_document_cache(dt)

		for column, value in to_update.items():
			query = query.set(column, value)

		query.run(debug=debug)

		if dt in self.value_cache:
			del self.value_cache[dt]

	def set_global(self, key, val, user="__global"):
		"""Save a global key value. Global values will be automatically set if they match fieldname."""
		self.set_default(key, val, user)

	def get_global(self, key, user="__global"):
		"""Return a global key value."""
		return self.get_default(key, user)

	def get_default(self, key, parent="__default"):
		"""Return default value as a list if multiple or single."""
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
		if self._disable_transaction_control:
			warnings.warn(message=TRANSACTION_DISABLED_MSG, stacklevel=2)
			return

		self.before_rollback.reset()
		self.after_rollback.reset()

		self.before_commit.run()

		self.sql("commit")
		self.begin()  # explicitly start a new transaction

		self.after_commit.run()

	def rollback(self, *, save_point=None):
		"""`ROLLBACK` current transaction. Optionally rollback to a known save_point."""
		if save_point:
			self.sql(f"rollback to savepoint {save_point}")
		elif not self._disable_transaction_control:
			self.before_commit.reset()
			self.after_commit.reset()

			self.before_rollback.run()

			self.sql("rollback")
			self.begin()

			self.after_rollback.run()
		else:
			warnings.warn(message=TRANSACTION_DISABLED_MSG, stacklevel=2)

	def savepoint(self, save_point):
		"""Savepoints work as a nested transaction.

		Changes can be undone to a save point by doing frappe.db.rollback(save_point)

		Note: rollback watchers can not work with save points.
		        so only changes to database are undone when rolling back to a savepoint.
		        Avoid using savepoints when writing to filesystem."""
		self.sql(f"savepoint {save_point}")

	def release_savepoint(self, save_point):
		self.sql(f"release savepoint {save_point}")

	def field_exists(self, dt, fn):
		"""Return true of field exists."""
		return self.exists("DocField", {"fieldname": fn, "parent": dt})

	def table_exists(self, doctype, cached=True):
		"""Return True if table for given doctype exists."""
		return f"tab{doctype}" in self.get_tables(cached=cached)

	def has_table(self, doctype):
		return self.table_exists(doctype)

	def get_tables(self, cached=True):
		raise NotImplementedError

	def a_row_exists(self, doctype):
		"""Return True if at least one row exists."""
		return frappe.get_all(doctype, limit=1, order_by=None, as_list=True)

	def exists(self, dt, dn=None, cache=False, *, debug=False):
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

		return self.get_value(dt, dn, ignore=True, cache=cache, order_by=None, debug=debug)

	def count(self, dt, filters=None, debug=False, cache=False, distinct: bool = True):
		"""Return `COUNT(*)` for given DocType and filters."""
		if cache and not filters:
			cache_count = frappe.cache.get_value(f"doctype:count:{dt}")
			if cache_count is not None:
				return cache_count
		count = frappe.qb.get_query(
			table=dt,
			filters=filters,
			fields=Count("*"),
			distinct=distinct,
			validate_filters=True,
		).run(debug=debug)[0][0]
		if not filters and cache:
			frappe.cache.set_value(f"doctype:count:{dt}", count, expires_in_sec=86400)
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
		"""Return list of column names from given table."""
		columns = frappe.cache.hget("table_columns", table)
		if columns is None:
			information_schema = frappe.qb.Schema("information_schema")

			columns = (
				frappe.qb.from_(information_schema.columns)
				.select(information_schema.columns.column_name)
				.where(information_schema.columns.table_name == table)
				.run(pluck=True)
			)

			if columns:
				frappe.cache.hset("table_columns", table, columns)

		return columns

	def get_table_columns(self, doctype):
		"""Return list of column names from given doctype."""
		columns = self.get_db_table_columns("tab" + doctype)
		if not columns:
			raise self.TableMissingError("DocType", doctype)
		return columns

	def has_column(self, doctype, column):
		"""Return True if column exists in database."""
		return column in self.get_table_columns(doctype)

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
		"""Escape quotes and percent in given string."""
		# implemented in specific class
		raise NotImplementedError

	from frappe.deprecation_dumpster import is_column_missing as _is_column_missing

	is_column_missing = staticmethod(_is_column_missing)

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

	def delete(self, doctype: str, filters: dict | list | None = None, debug=False, **kwargs):
		"""Delete rows from a table in site which match the passed filters. This
		does not trigger DocType hooks. Simply runs a DELETE query in the database.

		Doctype name can be passed directly, it will be pre-pended with `tab`.
		"""
		filters = filters or kwargs.get("conditions")
		query = frappe.qb.get_query(
			table=doctype,
			filters=filters,
			delete=True,
			validate_filters=True,
		)
		if "debug" not in kwargs:
			kwargs["debug"] = debug
		return query.run(**kwargs)

	def truncate(self, doctype: str):
		"""Truncate a table in the database. This runs a DDL command `TRUNCATE TABLE`.
		This cannot be rolled back.

		Doctype name can be passed directly, it will be pre-pended with `tab`.
		"""
		return self.sql_ddl(f"truncate `{get_table_name(doctype)}`")

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

			# ([`"]?) Captures " or ` at the beginning of the table name (if provided)
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

	def bulk_insert(
		self,
		doctype: str,
		fields: list[str],
		values: Iterable[Sequence[Any]],
		ignore_duplicates=False,
		*,
		chunk_size=10_000,
	):
		"""
		Insert multiple records at a time

		:param doctype: Doctype name
		:param fields: list of fields
		:params values: iterable of values
		"""
		table = frappe.qb.DocType(doctype)

		query = frappe.qb.into(table).columns(fields)

		if ignore_duplicates:
			# Pypika does not have same api for ignoring duplicates
			if frappe.conf.db_type == "mariadb":
				query = query.ignore()
			elif frappe.conf.db_type == "postgres":
				query = query.on_conflict().do_nothing()

		value_iterator = iter(values)
		while value_chunk := tuple(itertools.islice(value_iterator, chunk_size)):
			query.insert(*value_chunk).run()

	def create_sequence(self, *args, **kwargs):
		from frappe.database.sequence import create_sequence

		return create_sequence(*args, **kwargs)

	def set_next_sequence_val(self, *args, **kwargs):
		from frappe.database.sequence import set_next_val

		set_next_val(*args, **kwargs)

	def get_next_sequence_val(self, *args, **kwargs):
		from frappe.database.sequence import get_next_val

		return get_next_val(*args, **kwargs)

	def get_row_size(self, doctype: str) -> int:
		"""Get estimated max row size of any table in bytes."""
		raise NotImplementedError

	def rename_column(self, doctype: str, old_column_name: str, new_column_name: str):
		raise NotImplementedError

	@contextmanager
	def unbuffered_cursor(self):
		"""Context manager to temporarily use unbuffered cursor.

		Using this with `as_iterator=True` provides O(1) memory usage while reading large result sets.

		NOTE: You MUST do entire result set processing in the context, otherwise underlying cursor
		will be switched and you'll not get complete results.

		Usage:
		        with frappe.db.unbuffered_cursor():
		                for row in frappe.db.sql("query with huge result", as_iterator=True):
		                        continue # Do some processing.
		"""
		raise NotImplementedError


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
