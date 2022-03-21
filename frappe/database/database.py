# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

# Database Module
# --------------------

import datetime
import random
import re
import string
from contextlib import contextmanager
from time import time
from typing import Dict, List, Tuple, Union

from pypika.terms import Criterion, NullValue, PseudoColumn

import frappe
import frappe.defaults
import frappe.model.meta
from frappe import _
from frappe.model.utils.link_count import flush_local_link_count
from frappe.query_builder.functions import Count
from frappe.query_builder.utils import DocType
from frappe.utils import cast, get_datetime, getdate, now, sbool

from .query import Query


class Database(object):
	"""
	   Open a database connection with the given parmeters, if use_default is True, use the
	   login details from `conf.py`. This is called by the request handler and is accessible using
	   the `db` global variable. the `sql` method is also global to run queries
	"""
	VARCHAR_LEN = 140
	MAX_COLUMN_LENGTH = 64

	OPTIONAL_COLUMNS = ["_user_tags", "_comments", "_assign", "_liked_by"]
	DEFAULT_SHORTCUTS = ['_Login', '__user', '_Full Name', 'Today', '__today', "now", "Now"]
	STANDARD_VARCHAR_COLUMNS = ('name', 'owner', 'modified_by')
	DEFAULT_COLUMNS = ['name', 'creation', 'modified', 'modified_by', 'owner', 'docstatus', 'idx']
	CHILD_TABLE_COLUMNS = ('parent', 'parenttype', 'parentfield')
	MAX_WRITES_PER_TRANSACTION = 200_000

	class InvalidColumnName(frappe.ValidationError): pass


	def __init__(self, host=None, user=None, password=None, ac_name=None, use_default=0, port=None):
		self.setup_type_map()
		self.host = host or frappe.conf.db_host or '127.0.0.1'
		self.port = port or frappe.conf.db_port or ''
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
		self.query = Query()

	def setup_type_map(self):
		pass

	def connect(self):
		"""Connects to a database as set in `site_config.json`."""
		self.cur_db_name = self.user
		self._conn = self.get_connection()
		self._cursor = self._conn.cursor()
		frappe.local.rollback_observers = []

	def use(self, db_name):
		"""`USE` db_name."""
		self._conn.select_db(db_name)

	def get_connection(self):
		pass

	def get_database_size(self):
		pass

	def sql(self, query, values=(), as_dict = 0, as_list = 0, formatted = 0,
			debug=0, ignore_ddl=0, as_utf8=0, auto_commit=0, update=None,
			explain=False, run=True, pluck=False):
		"""Execute a SQL query and fetch all rows.

		:param query: SQL query.
		:param values: List / dict of values to be escaped and substituted in the query.
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
		query = str(query)
		if not run:
			return query

		if re.search(r'ifnull\(', query, flags=re.IGNORECASE):
			# replaces ifnull in query with coalesce
			query = re.sub(r'ifnull\(', 'coalesce(', query, flags=re.IGNORECASE)

		if not self._conn:
			self.connect()

		# in transaction validations
		self.check_transaction_status(query)

		self.clear_db_table_cache(query)

		# autocommit
		if auto_commit: self.commit()

		# execute
		try:
			if debug:
				time_start = time()

			self.log_query(query, values, debug, explain)

			if values!=():

				# MySQL-python==1.2.5 hack!
				if not isinstance(values, (dict, tuple, list)):
					values = (values,)

				self._cursor.execute(query, values)

				if frappe.flags.in_migrate:
					self.log_touched_tables(query, values)

			else:
				self._cursor.execute(query)

				if frappe.flags.in_migrate:
					self.log_touched_tables(query)

			if debug:
				time_end = time()
				frappe.errprint(("Execution time: {0} sec").format(round(time_end - time_start, 2)))

		except Exception as e:
			if self.is_syntax_error(e):
				# only for mariadb
				frappe.errprint('Syntax error in query:')
				frappe.errprint(query)

			elif self.is_deadlocked(e):
				raise frappe.QueryDeadlockError(e)

			elif self.is_timedout(e):
				raise frappe.QueryTimeoutError(e)

			elif frappe.conf.db_type == 'postgres':
				# TODO: added temporarily
				print(e)
				raise

			if ignore_ddl and (self.is_missing_column(e) or self.is_table_missing(e) or self.cant_drop_field_or_key(e)):
				pass
			else:
				raise

		if auto_commit: self.commit()

		if not self._cursor.description:
			return ()

		if pluck:
			return [r[0] for r in self._cursor.fetchall()]

		# scrub output if required
		if as_dict:
			ret = self.fetch_as_dict(formatted, as_utf8)
			if update:
				for r in ret:
					r.update(update)
			return ret
		elif as_list:
			return self.convert_to_lists(self._cursor.fetchall(), formatted, as_utf8)
		elif as_utf8:
			return self.convert_to_lists(self._cursor.fetchall(), formatted, as_utf8)
		else:
			return self._cursor.fetchall()

	def log_query(self, query, values, debug, explain):
		# for debugging in tests
		if frappe.conf.get('allow_tests') and frappe.cache().get_value('flag_print_sql'):
			print(self.mogrify(query, values))

		# debug
		if debug:
			if explain and query.strip().lower().startswith('select'):
				self.explain_query(query, values)
			frappe.errprint(self.mogrify(query, values))

		# info
		if (frappe.conf.get("logging") or False)==2:
			frappe.log("<<<< query")
			frappe.log(self.mogrify(query, values))
			frappe.log(">>>>")

	def mogrify(self, query, values):
		'''build the query string with values'''
		if not values:
			return query
		else:
			try:
				return self._cursor.mogrify(query, values)
			except: # noqa: E722
				return (query, values)

	def explain_query(self, query, values=None):
		"""Print `EXPLAIN` in error log."""
		try:
			frappe.errprint("--- query explain ---")
			if values is None:
				self._cursor.execute("explain " + query)
			else:
				self._cursor.execute("explain " + query, values)
			import json
			frappe.errprint(json.dumps(self.fetch_as_dict(), indent=1))
			frappe.errprint("--- query explain end ---")
		except Exception:
			frappe.errprint("error in query explain")

	def sql_list(self, query, values=(), debug=False, **kwargs):
		"""Return data as list of single elements (first column).

		Example:

			# doctypes = ["DocType", "DocField", "User", ...]
			doctypes = frappe.db.sql_list("select name from DocType")
		"""
		return [r[0] for r in self.sql(query, values, **kwargs, debug=debug)]

	def sql_ddl(self, query, values=(), debug=False):
		"""Commit and execute a query. DDL (Data Definition Language) queries that alter schema
		autocommit in MariaDB."""
		self.commit()
		self.sql(query, debug=debug)


	def check_transaction_status(self, query):
		"""Raises exception if more than 20,000 `INSERT`, `UPDATE` queries are
		executed in one transaction. This is to ensure that writes are always flushed otherwise this
		could cause the system to hang."""
		self.check_implicit_commit(query)

		if query and query.strip().lower() in ('commit', 'rollback'):
			self.transaction_writes = 0

		if query[:6].lower() in ('update', 'insert', 'delete'):
			self.transaction_writes += 1
			if self.transaction_writes > self.MAX_WRITES_PER_TRANSACTION:
				if self.auto_commit_on_many_writes:
					self.commit()
				else:
					msg = "<br><br>" + _("Too many changes to database in single action.") + "<br>"
					msg += _("The changes have been reverted.") + "<br>"
					raise frappe.TooManyWritesError(msg)

	def check_implicit_commit(self, query):
		if self.transaction_writes and \
			query and query.strip().split()[0].lower() in ['start', 'alter', 'drop', 'create', "begin", "truncate"]:
			raise Exception('This statement can cause implicit commit')

	def fetch_as_dict(self, formatted=0, as_utf8=0):
		"""Internal. Converts results to dict."""
		result = self._cursor.fetchall()
		ret = []
		if result:
			keys = [column[0] for column in self._cursor.description]

		for r in result:
			values = []
			for value in r:
				if as_utf8 and isinstance(value, str):
					value = value.encode('utf-8')
				values.append(value)

			ret.append(frappe._dict(zip(keys, values)))
		return ret

	@staticmethod
	def clear_db_table_cache(query):
		if query and query.strip().split()[0].lower() in {'drop', 'create'}:
			frappe.cache().delete_key('db_tables')

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
		nres = []
		for r in res:
			nr = []
			for val in r:
				if as_utf8 and isinstance(val, str):
					val = val.encode('utf-8')
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
		order_by="KEEP_DEFAULT_ORDERING",
		cache=False,
		for_update=False,
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

		ret = self.get_values(doctype, filters, fieldname, ignore, as_dict, debug,
			order_by, cache=cache, for_update=for_update, run=run, pluck=pluck, distinct=distinct)

		if not run:
			return ret

		return ((len(ret[0]) > 1 or as_dict) and ret[0] or ret[0][0]) if ret else None

	def get_values(self, doctype, filters=None, fieldname="name", ignore=None, as_dict=False,
		debug=False, order_by="KEEP_DEFAULT_ORDERING", update=None, cache=False, for_update=False,
		run=True, pluck=False, distinct=False):
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
		if cache and isinstance(filters, str) and \
			(doctype, filters, fieldname) in self.value_cache:
			return self.value_cache[(doctype, filters, fieldname)]

		if distinct:
			order_by = None

		if isinstance(filters, list):
			out = self._get_value_for_many_names(
				doctype,
				filters,
				fieldname,
				order_by,
				debug=debug,
				run=run,
				pluck=pluck,
				distinct=distinct,
			)

		else:
			fields = fieldname
			if fieldname != "*":
				if isinstance(fieldname, str):
					fields = [fieldname]

			if (filters is not None) and (filters!=doctype or doctype=="DocType"):
				try:
					if order_by:
						order_by = "modified" if order_by == "KEEP_DEFAULT_ORDERING" else order_by
					out = self._get_values_from_table(
						fields,
						filters,
						doctype,
						as_dict,
						debug,
						order_by,
						update,
						for_update=for_update,
						run=run,
						pluck=pluck,
						distinct=distinct
					)
				except Exception as e:
					if ignore and (frappe.db.is_missing_column(e) or frappe.db.is_table_missing(e)):
						# table or column not found, return None
						out = None
					elif (not ignore) and frappe.db.is_table_missing(e):
						# table not found, look in singles
						out = self.get_values_from_single(fields, filters, doctype, as_dict, debug, update, run=run, distinct=distinct)

					else:
						raise
			else:
				out = self.get_values_from_single(fields, filters, doctype, as_dict, debug, update, run=run, pluck=pluck, distinct=distinct)

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
		run=True,
		pluck=False,
		distinct=False,
	):
		"""Get values from `tabSingles` (Single DocTypes) (internal).

		:param fields: List of fields,
		:param filters: Filters (dict).
		:param doctype: DocType name.
		"""
		# TODO
		# if not frappe.model.meta.is_single(doctype):
		# 	raise frappe.DoesNotExistError("DocType", doctype)

		if fields=="*" or isinstance(filters, dict):
			# check if single doc matches with filters
			values = self.get_singles_dict(doctype)
			if isinstance(filters, dict):
				for key, value in filters.items():
					if values.get(key) != value:
						return []

			if as_dict:
				return values and [values] or []

			if isinstance(fields, list):
				return [map(values.get, fields)]

		else:
			r = self.query.get_sql(
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


	def get_singles_dict(self, doctype, debug = False):
		"""Get Single DocType as dict.

		:param doctype: DocType of the single object whose value is requested

		Example:

			# Get coulmn and value of the single doctype Accounts Settings
			account_settings = frappe.db.get_singles_dict("Accounts Settings")
		"""
		result = self.query.get_sql(
			"Singles", filters={"doctype": doctype}, fields=["field", "value"]
		).run()
		dict_  = frappe._dict(result)
		return dict_

	@staticmethod
	def get_all(*args, **kwargs):
		return frappe.get_all(*args, **kwargs)

	@staticmethod
	def get_list(*args, **kwargs):
		return frappe.get_list(*args, **kwargs)

	def set_single_value(self, doctype, fieldname, value, *args, **kwargs):
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

		val = self.query.get_sql(
			table="Singles",
			filters={"doctype": doctype, "field": fieldname},
			fields="value",
		).run()
		val = val[0][0] if val else None

		df = frappe.get_meta(doctype).get_field(fieldname)

		if not df:
			frappe.throw(_('Invalid field name: {0}').format(frappe.bold(fieldname)), self.InvalidColumnName)

		val = cast(df.fieldtype, val)

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
		debug,
		order_by=None,
		update=None,
		for_update=False,
		run=True,
		pluck=False,
		distinct=False,
	):
		field_objects = []

		if not isinstance(fields, Criterion):
			for field in fields:
				if "(" in str(field) or " as " in str(field):
					field_objects.append(PseudoColumn(field))
				else:
					field_objects.append(field)

		query = self.query.get_sql(
			table=doctype,
			filters=filters,
			orderby=order_by,
			for_update=for_update,
			field_objects=field_objects,
			fields=fields,
			distinct=distinct,
		)
		if (
			fields == "*"
			and not isinstance(fields, (list, tuple))
			and not isinstance(fields, Criterion)
		):
			as_dict = True

		r = self.sql(
			query, as_dict=as_dict, debug=debug, update=update, run=run, pluck=pluck
		)
		return r

	def _get_value_for_many_names(self, doctype, names, field, order_by, debug=False, run=True, pluck=False, distinct=False):
		names = list(filter(None, names))
		if names:
			return self.get_all(
				doctype,
				fields=field,
				filters=names,
				order_by=order_by,
				pluck=pluck,
				debug=debug,
				as_list=1,
				run=run,
				distinct=distinct,
			)
		else:
			return {}

	def update(self, *args, **kwargs):
		"""Update multiple values. Alias for `set_value`."""
		return self.set_value(*args, **kwargs)

	def set_value(self, dt, dn, field, val=None, modified=None, modified_by=None,
		update_modified=True, debug=False, for_update=True):
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
		:param for_update: Will add a row-level lock to the value that is being set so that it can be released on commit.
		"""
		is_single_doctype = not (dn and dt != dn)
		to_update = field if isinstance(field, dict) else {field: val}

		if update_modified:
			modified = modified or now()
			modified_by = modified_by or frappe.session.user
			to_update.update({"modified": modified, "modified_by": modified_by})

		if is_single_doctype:
			frappe.db.delete(
				"Singles",
				filters={"field": ("in", tuple(to_update)), "doctype": dt}, debug=debug
			)

			singles_data = ((dt, key, sbool(value)) for key, value in to_update.items())
			query = (
				frappe.qb.into("Singles")
					.columns("doctype", "field", "value")
					.insert(*singles_data)
			).run(debug=debug)
			frappe.clear_document_cache(dt, dt)

		else:
			table = DocType(dt)

			if for_update:
				docnames = tuple(
					self.get_values(dt, dn, "name", debug=debug, for_update=for_update, pluck=True)
				) or (NullValue(),)
				query = frappe.qb.update(table).where(table.name.isin(docnames))

				for docname in docnames:
					frappe.clear_document_cache(dt, docname)

			else:
				query = self.query.build_conditions(table=dt, filters=dn, update=True)
				# TODO: Fix this; doesn't work rn - gavin@frappe.io
				# frappe.cache().hdel_keys(dt, "document_cache")
				# Workaround: clear all document caches
				frappe.cache().delete_value('document_cache')

			for column, value in to_update.items():
				query = query.set(column, value)

			query.run(debug=debug)

		if dt in self.value_cache:
			del self.value_cache[dt]

	@staticmethod
	def set(doc, field, val):
		"""Set value in document. **Avoid**"""
		doc.db_set(field, val)

	def touch(self, doctype, docname):
		"""Update the modified timestamp of this document."""
		modified = now()
		self.sql("""update `tab{doctype}` set `modified`=%s
			where name=%s""".format(doctype=doctype), (modified, docname))
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

	def set_global(self, key, val, user='__global'):
		"""Save a global key value. Global values will be automatically set if they match fieldname."""
		self.set_default(key, val, user)

	def get_global(self, key, user='__global'):
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
		if key:
			defaults = frappe.defaults.get_defaults(parent)
			d = defaults.get(key, None)
			if(not d and key != frappe.scrub(key)):
				d = defaults.get(frappe.scrub(key), None)
			return d
		else:
			return frappe.defaults.get_defaults(parent)

	def begin(self):
		self.sql("START TRANSACTION")

	def commit(self):
		"""Commit current transaction. Calls SQL `COMMIT`."""
		for method in frappe.local.before_commit:
			frappe.call(method[0], *(method[1] or []), **(method[2] or {}))

		self.sql("commit")

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
			for obj in frappe.local.rollback_observers:
				if hasattr(obj, "on_rollback"):
					obj.on_rollback()
			frappe.local.rollback_observers = []

	def field_exists(self, dt, fn):
		"""Return true of field exists."""
		return self.exists('DocField', {
			'fieldname': fn,
			'parent': dt
		})

	def table_exists(self, doctype, cached=True):
		"""Returns True if table for given doctype exists."""
		return ("tab" + doctype) in self.get_tables(cached=cached)

	def has_table(self, doctype):
		return self.table_exists(doctype)

	def get_tables(self, cached=True):
		tables = frappe.cache().get_value('db_tables')
		if not tables or not cached:
			table_rows = self.sql("""
				SELECT table_name
				FROM information_schema.tables
				WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
			""")
			tables = {d[0] for d in table_rows}
			frappe.cache().set_value('db_tables', tables)
		return tables

	def a_row_exists(self, doctype):
		"""Returns True if atleast one row exists."""
		return self.sql("select name from `tab{doctype}` limit 1".format(doctype=doctype))

	def exists(self, dt, dn=None, cache=False):
		"""Returns true if document exists.

		:param dt: DocType name.
		:param dn: Document name or filter dict."""
		if isinstance(dt, str):
			if dt!="DocType" and dt==dn:
				return True # single always exists (!)
			try:
				return self.get_value(dt, dn, "name", cache=cache)
			except Exception:
				return None

		elif isinstance(dt, dict) and dt.get('doctype'):
			try:
				conditions = []
				for d in dt:
					if d == 'doctype': continue
					conditions.append([d, '=', dt[d]])
				return self.get_all(dt['doctype'], filters=conditions, as_list=1)
			except Exception:
				return None

	def count(self, dt, filters=None, debug=False, cache=False):
		"""Returns `COUNT(*)` for given DocType and filters."""
		if cache and not filters:
			cache_count = frappe.cache().get_value('doctype:count:{}'.format(dt))
			if cache_count is not None:
				return cache_count
		query = self.query.get_sql(table=dt, filters=filters, fields=Count("*"))
		if filters:
			count = self.sql(query, debug=debug)[0][0]
			return count
		else:
			count = self.sql(query, debug=debug)[0][0]
			if cache:
				frappe.cache().set_value('doctype:count:{}'.format(dt), count, expires_in_sec = 86400)
			return count

	@staticmethod
	def format_date(date):
		return getdate(date).strftime("%Y-%m-%d")

	@staticmethod
	def format_datetime(datetime):
		if not datetime:
			return '0001-01-01 00:00:00.000000'

		if isinstance(datetime, str):
			if ':' not in datetime:
				datetime = datetime + ' 00:00:00.000000'
		else:
			datetime = datetime.strftime("%Y-%m-%d %H:%M:%S.%f")

		return datetime

	def get_creation_count(self, doctype, minutes):
		"""Get count of records created in the last x minutes"""
		from frappe.utils import now_datetime
		from dateutil.relativedelta import relativedelta

		return self.sql("""select count(name) from `tab{doctype}`
			where creation >= %s""".format(doctype=doctype),
			now_datetime() - relativedelta(minutes=minutes))[0][0]

	def get_db_table_columns(self, table):
		"""Returns list of column names from given table."""
		columns = frappe.cache().hget('table_columns', table)
		if columns is None:
			columns = [r[0] for r in self.sql('''
				select column_name
				from information_schema.columns
				where table_name = %s ''', table)]

			if columns:
				frappe.cache().hset('table_columns', table, columns)

		return columns

	def get_table_columns(self, doctype):
		"""Returns list of column names from given doctype."""
		columns = self.get_db_table_columns('tab' + doctype)
		if not columns:
			raise self.TableMissingError('DocType', doctype)
		return columns

	def has_column(self, doctype, column):
		"""Returns True if column exists in database."""
		return column in self.get_table_columns(doctype)

	def get_column_type(self, doctype, column):
		return self.sql('''SELECT column_type FROM INFORMATION_SCHEMA.COLUMNS
			WHERE table_name = 'tab{0}' AND column_name = '{1}' '''.format(doctype, column))[0][0]

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
		index_name = re.sub(r"\s*\([^)]+\)\s*", r"", index_name)
		return index_name

	def get_system_setting(self, key):
		def _load_system_settings():
			return self.get_singles_dict("System Settings")
		return frappe.cache().get_value("system_settings", _load_system_settings).get(key)

	def close(self):
		"""Close database connection."""
		if self._conn:
			# self._cursor.close()
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
		'''Return descendants of the current record'''
		node_location_indexes = self.get_value(doctype, name, ('lft', 'rgt'))
		if node_location_indexes:
			lft, rgt = node_location_indexes
			return self.sql_list('''select name from `tab{doctype}`
				where lft > {lft} and rgt < {rgt}'''.format(doctype=doctype, lft=lft, rgt=rgt))
		else:
			# when document does not exist
			return []

	def is_missing_table_or_column(self, e):
		return self.is_missing_column(e) or self.is_table_missing(e)

	def multisql(self, sql_dict, values=(), **kwargs):
		current_dialect = frappe.db.db_type or 'mariadb'
		query = sql_dict.get(current_dialect)
		return self.sql(query, values, **kwargs)

	def delete(self, doctype: str, filters: Union[Dict, List] = None, debug=False, **kwargs):
		"""Delete rows from a table in site which match the passed filters. This
		does trigger DocType hooks. Simply runs a DELETE query in the database.

		Doctype name can be passed directly, it will be pre-pended with `tab`.
		"""
		values = ()
		filters = filters or kwargs.get("conditions")
		query = self.query.build_conditions(table=doctype, filters=filters).delete()
		if "debug" not in kwargs:
			kwargs["debug"] = debug
		return self.sql(query, values, **kwargs)

	def truncate(self, doctype: str):
		"""Truncate a table in the database. This runs a DDL command `TRUNCATE TABLE`.
		This cannot be rolled back.

		Doctype name can be passed directly, it will be pre-pended with `tab`.
		"""
		table = doctype if doctype.startswith("__") else f"tab{doctype}"
		return self.sql_ddl(f"truncate `{table}`")

	def clear_table(self, doctype):
		return self.truncate(doctype)

	def get_last_created(self, doctype):
		last_record = self.get_all(doctype, ('creation'), limit=1, order_by='creation desc')
		if last_record:
			return get_datetime(last_record[0].creation)
		else:
			return None

	def log_touched_tables(self, query, values=None):
		if values:
			query = frappe.safe_decode(self._cursor.mogrify(query, values))
		if query.strip().lower().split()[0] in ('insert', 'delete', 'update', 'alter', 'drop', 'rename'):
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

			single_word_regex = r'([`"]?)(tab([A-Z]\w+))\1'
			multi_word_regex = r'([`"])(tab([A-Z]\w+)( [A-Z]\w+)+)\1'
			tables = []
			for regex in (single_word_regex, multi_word_regex):
				tables += [groups[1] for groups in re.findall(regex, query)]

			if frappe.flags.touched_tables is None:
				frappe.flags.touched_tables = set()
			frappe.flags.touched_tables.update(tables)

	def bulk_insert(self, doctype, fields, values, ignore_duplicates=False):
		"""
			Insert multiple records at a time

			:param doctype: Doctype name
			:param fields: list of fields
			:params values: list of list of values
		"""
		insert_list = []
		fields = ", ".join("`"+field+"`" for field in fields)

		for idx, value in enumerate(values):
			insert_list.append(tuple(value))
			if idx and (idx%10000 == 0 or idx < len(values)-1):
				self.sql("""INSERT {ignore_duplicates} INTO `tab{doctype}` ({fields}) VALUES {values}""".format(
						ignore_duplicates="IGNORE" if ignore_duplicates else "",
						doctype=doctype,
						fields=fields,
						values=", ".join(['%s'] * len(insert_list))
					), tuple(insert_list))
				insert_list = []


def enqueue_jobs_after_commit():
	from frappe.utils.background_jobs import execute_job, get_queue

	if frappe.flags.enqueue_after_commit and len(frappe.flags.enqueue_after_commit) > 0:
		for job in frappe.flags.enqueue_after_commit:
			q = get_queue(job.get("queue"), is_async=job.get("is_async"))
			q.enqueue_call(execute_job, timeout=job.get("timeout"),
							kwargs=job.get("queue_args"))
		frappe.flags.enqueue_after_commit = []

@contextmanager
def savepoint(catch: Union[type, Tuple[type, ...]] = Exception):
	""" Wrapper for wrapping blocks of DB operations in a savepoint.

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
		savepoint = ''.join(random.sample(string.ascii_lowercase, 10))
		frappe.db.savepoint(savepoint)
		yield # control back to calling function
	except catch:
		frappe.db.rollback(save_point=savepoint)
	else:
		frappe.db.release_savepoint(savepoint)
