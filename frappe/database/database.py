# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# Database Module
# --------------------

from __future__ import unicode_literals

import re
import time
import frappe
import datetime
import frappe.defaults
import frappe.model.meta

from frappe import _
from time import time
from frappe.utils import now, getdate, cast_fieldtype, get_datetime
from frappe.utils.background_jobs import execute_job, get_queue
from frappe.model.utils.link_count import flush_local_link_count
from frappe.utils import cint

# imports - compatibility imports
from six import (
	integer_types,
	string_types,
	text_type,
	iteritems
)

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
	STANDARD_VARCHAR_COLUMNS = ('name', 'owner', 'modified_by', 'parent', 'parentfield', 'parenttype')
	DEFAULT_COLUMNS = ['name', 'creation', 'modified', 'modified_by', 'owner', 'docstatus', 'parent',
		'parentfield', 'parenttype', 'idx']

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
		debug=0, ignore_ddl=0, as_utf8=0, auto_commit=0, update=None, explain=False):
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

		Examples:

			# return customer names as dicts
			frappe.db.sql("select name from tabCustomer", as_dict=True)

			# return names beginning with a
			frappe.db.sql("select name from tabCustomer where name like %s", "a%")

			# values as dict
			frappe.db.sql("select name from tabCustomer where name like %(name)s and owner=%(owner)s",
				{"name": "a%", "owner":"test@example.com"})

		"""
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
				if isinstance(values, dict):
					values = dict(values)

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
			if frappe.conf.db_type == 'postgres':
				self.rollback()

			elif self.is_syntax_error(e):
				# only for mariadb
				frappe.errprint('Syntax error in query:')
				frappe.errprint(query)

			if ignore_ddl and (self.is_missing_column(e) or self.is_missing_table(e) or self.cant_drop_field_or_key(e)):
				pass
			else:
				raise

		if auto_commit: self.commit()

		if not self._cursor.description:
			return ()

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

	def sql_list(self, query, values=(), debug=False):
		"""Return data as list of single elements (first column).

		Example:

			# doctypes = ["DocType", "DocField", "User", ...]
			doctypes = frappe.db.sql_list("select name from DocType")
		"""
		return [r[0] for r in self.sql(query, values, debug=debug)]

	def sql_ddl(self, query, values=(), debug=False):
		"""Commit and execute a query. DDL (Data Definition Language) queries that alter schema
		autocommit in MariaDB."""
		self.commit()
		self.sql(query, debug=debug)

	def check_transaction_status(self, query):
		"""Raises exception if more than 20,000 `INSERT`, `UPDATE` queries are
		executed in one transaction. This is to ensure that writes are always flushed otherwise this
		could cause the system to hang."""
		if self.transaction_writes and \
			query and query.strip().split()[0].lower() in ['start', 'alter', 'drop', 'create', "begin", "truncate"]:
			raise Exception('This statement can cause implicit commit')

		if query and query.strip().lower() in ('commit', 'rollback'):
			self.transaction_writes = 0

		if query[:6].lower() in ('update', 'insert', 'delete'):
			self.transaction_writes += 1
			if self.transaction_writes > 200000:
				if self.auto_commit_on_many_writes:
					self.commit()
				else:
					frappe.throw(_("Too many writes in one request. Please send smaller requests"), frappe.ValidationError)

	def fetch_as_dict(self, formatted=0, as_utf8=0):
		"""Internal. Converts results to dict."""
		result = self._cursor.fetchall()
		ret = []
		if result:
			keys = [column[0] for column in self._cursor.description]

		for r in result:
			values = []
			for value in r:
				if as_utf8 and isinstance(value, text_type):
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
				if isinstance(v, (datetime.date, datetime.timedelta, datetime.datetime, integer_types)):
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
				if as_utf8 and isinstance(val, text_type):
					val = val.encode('utf-8')
				nr.append(val)
			nres.append(nr)
		return nres

	def build_conditions(self, filters):
		"""Convert filters sent as dict, lists to SQL conditions. filter's key
		is passed by map function, build conditions like:

		* ifnull(`fieldname`, default_value) = %(fieldname)s
		* `fieldname` [=, !=, >, >=, <, <=] %(fieldname)s
		"""
		conditions = []
		values = {}
		def _build_condition(key):
			"""
				filter's key is passed by map function
				build conditions like:
					* ifnull(`fieldname`, default_value) = %(fieldname)s
					* `fieldname` [=, !=, >, >=, <, <=] %(fieldname)s
			"""
			_operator = "="
			_rhs = " %(" + key + ")s"
			value = filters.get(key)
			values[key] = value
			if isinstance(value, (list, tuple)):
				# value is a tuple like ("!=", 0)
				_operator = value[0]
				values[key] = value[1]
				if isinstance(value[1], (tuple, list)):
					# value is a list in tuple ("in", ("A", "B"))
					_rhs = " ({0})".format(", ".join([self.escape(v) for v in value[1]]))
					del values[key]

			if _operator not in ["=", "!=", ">", ">=", "<", "<=", "like", "in", "not in", "not like"]:
				_operator = "="

			if "[" in key:
				split_key = key.split("[")
				condition = "coalesce(`" + split_key[0] + "`, " + split_key[1][:-1] + ") " \
					+ _operator + _rhs
			else:
				condition = "`" + key + "` " + _operator + _rhs

			conditions.append(condition)

		if isinstance(filters, int):
			# docname is a number, convert to string
			filters = str(filters)

		if isinstance(filters, string_types):
			filters = { "name": filters }

		for f in filters:
			_build_condition(f)

		return " and ".join(conditions), values

	def get(self, doctype, filters=None, as_dict=True, cache=False):
		"""Returns `get_value` with fieldname='*'"""
		return self.get_value(doctype, filters, "*", as_dict=as_dict, cache=cache)

	def get_value(self, doctype, filters=None, fieldname="name", ignore=None, as_dict=False,
		debug=False, order_by=None, cache=False, for_update=False):
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
			order_by, cache=cache, for_update=for_update)

		return ((len(ret[0]) > 1 or as_dict) and ret[0] or ret[0][0]) if ret else None

	def get_values(self, doctype, filters=None, fieldname="name", ignore=None, as_dict=False,
		debug=False, order_by=None, update=None, cache=False, for_update=False):
		"""Returns multiple document properties.

		:param doctype: DocType name.
		:param filters: Filters like `{"x":"y"}` or name of the document.
		:param fieldname: Column name.
		:param ignore: Don't raise exception if table, column is missing.
		:param as_dict: Return values as dict.
		:param debug: Print query in error log.
		:param order_by: Column to order by

		Example:

			# return first customer starting with a
			customers = frappe.db.get_values("Customer", {"name": ("like a%")})

			# return last login of **User** `test@example.com`
			user = frappe.db.get_values("User", "test@example.com", "*")[0]
		"""
		out = None
		if cache and isinstance(filters, string_types) and \
			(doctype, filters, fieldname) in self.value_cache:
			return self.value_cache[(doctype, filters, fieldname)]

		if not order_by: order_by = 'modified desc'

		if isinstance(filters, list):
			out = self._get_value_for_many_names(doctype, filters, fieldname, debug=debug)

		else:
			fields = fieldname
			if fieldname!="*":
				if isinstance(fieldname, string_types):
					fields = [fieldname]
				else:
					fields = fieldname

			if (filters is not None) and (filters!=doctype or doctype=="DocType"):
				try:
					out = self._get_values_from_table(fields, filters, doctype, as_dict, debug, order_by, update, for_update=for_update)
				except Exception as e:
					if ignore and (frappe.db.is_missing_column(e) or frappe.db.is_table_missing(e)):
						# table or column not found, return None
						out = None
					elif (not ignore) and frappe.db.is_table_missing(e):
						# table not found, look in singles
						out = self.get_values_from_single(fields, filters, doctype, as_dict, debug, update)
					else:
						raise
			else:
				out = self.get_values_from_single(fields, filters, doctype, as_dict, debug, update)

		if cache and isinstance(filters, string_types):
			self.value_cache[(doctype, filters, fieldname)] = out

		return out

	def get_values_from_single(self, fields, filters, doctype, as_dict=False, debug=False, update=None):
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
			r = self.sql("""select field, value
				from `tabSingles` where field in (%s) and doctype=%s"""
					% (', '.join(['%s'] * len(fields)), '%s'),
					tuple(fields) + (doctype,), as_dict=False, debug=debug)

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
		result = self.sql("""
			SELECT field, value
			FROM   `tabSingles`
			WHERE  doctype = %s
		""", doctype)
		# result = _cast_result(doctype, result)

		dict_  = frappe._dict(result)

		return dict_

	@staticmethod
	def get_all(*args, **kwargs):
		return frappe.get_all(*args, **kwargs)

	@staticmethod
	def get_list(*args, **kwargs):
		return frappe.get_list(*args, **kwargs)

	def get_single_value(self, doctype, fieldname, cache=False):
		"""Get property of Single DocType. Cache locally by default

		:param doctype: DocType of the single object whose value is requested
		:param fieldname: `fieldname` of the property whose value is requested

		Example:

			# Get the default value of the company from the Global Defaults doctype.
			company = frappe.db.get_single_value('Global Defaults', 'default_company')
		"""

		if not doctype in self.value_cache:
			self.value_cache = self.value_cache[doctype] = {}

		if fieldname in self.value_cache[doctype]:
			return self.value_cache[doctype][fieldname]

		val = self.sql("""select `value` from
			`tabSingles` where `doctype`=%s and `field`=%s""", (doctype, fieldname))
		val = val[0][0] if val else None

		df = frappe.get_meta(doctype).get_field(fieldname)

		if not df:
			frappe.throw(_('Invalid field name: {0}').format(frappe.bold(fieldname)), self.InvalidColumnName)

		if df.fieldtype in frappe.model.numeric_fieldtypes:
			val = cint(val)

		self.value_cache[doctype][fieldname] = val

		return val

	def get_singles_value(self, *args, **kwargs):
		"""Alias for get_single_value"""
		return self.get_single_value(*args, **kwargs)

	def _get_values_from_table(self, fields, filters, doctype, as_dict, debug, order_by=None, update=None, for_update=False):
		fl = []
		if isinstance(fields, (list, tuple)):
			for f in fields:
				if "(" in f or " as " in f: # function
					fl.append(f)
				else:
					fl.append("`" + f + "`")
			fl = ", ".join(fl)
		else:
			fl = fields
			if fields=="*":
				as_dict = True

		conditions, values = self.build_conditions(filters)

		order_by = ("order by " + order_by) if order_by else ""

		r = self.sql("select {fields} from `tab{doctype}` {where} {conditions} {order_by} {for_update}"
			.format(
				for_update = 'for update' if for_update else '',
				fields = fl,
				doctype = doctype,
				where = "where" if conditions else "",
				conditions = conditions,
				order_by = order_by),
			values, as_dict=as_dict, debug=debug, update=update)

		return r

	def _get_value_for_many_names(self, doctype, names, field, debug=False):
		names = list(filter(None, names))

		if names:
			return self.get_all(doctype,
				fields=['name', field],
				filters=[['name', 'in', names]],
				debug=debug, as_list=1)
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
		if not modified:
			modified = now()
		if not modified_by:
			modified_by = frappe.session.user

		to_update = {}
		if update_modified:
			to_update = {"modified": modified, "modified_by": modified_by}

		if isinstance(field, dict):
			to_update.update(field)
		else:
			to_update.update({field: val})

		if dn and dt!=dn:
			# with table
			set_values = []
			for key in to_update:
				set_values.append('`{0}`=%({0})s'.format(key))

			for name in self.get_values(dt, dn, 'name', for_update=for_update):
				values = dict(name=name[0])
				values.update(to_update)

				self.sql("""update `tab{0}`
					set {1} where name=%(name)s""".format(dt, ', '.join(set_values)),
					values, debug=debug)
		else:
			# for singles
			keys = list(to_update)
			self.sql('''
				delete from `tabSingles`
				where field in ({0}) and
					doctype=%s'''.format(', '.join(['%s']*len(keys))),
					list(keys) + [dt], debug=debug)
			for key, value in iteritems(to_update):
				self.sql('''insert into `tabSingles` (doctype, field, value) values (%s, %s, %s)''',
					(dt, key, value), debug=debug)

		if dt in self.value_cache:
			del self.value_cache[dt]

		frappe.clear_document_cache(dt, dn)

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

	def rollback(self):
		"""`ROLLBACK` current transaction."""
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

	def table_exists(self, doctype):
		"""Returns True if table for given doctype exists."""
		return ("tab" + doctype) in self.get_tables()

	def has_table(self, doctype):
		return self.table_exists(doctype)

	def get_tables(self):
		tables = frappe.cache().get_value('db_tables')
		if not tables:
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
		if isinstance(dt, string_types):
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
		if filters:
			conditions, filters = self.build_conditions(filters)
			count = self.sql("""select count(*)
				from `tab%s` where %s""" % (dt, conditions), filters, debug=debug)[0][0]
			return count
		else:
			count = self.sql("""select count(*)
				from `tab%s`""" % (dt,))[0][0]

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

		if isinstance(datetime, frappe.string_types):
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
		pass

	def add_index(self, doctype, fields, index_name=None):
		pass

	def add_unique(self, doctype, fields, constraint_name=None):
		pass

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
		pass

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
		return self.is_missing_column(e) or self.is_missing_table(e)

	def multisql(self, sql_dict, values=(), **kwargs):
		current_dialect = frappe.db.db_type or 'mariadb'
		query = sql_dict.get(current_dialect)
		return self.sql(query, values, **kwargs)

	def delete(self, doctype, conditions, debug=False):
		if conditions:
			conditions, values = self.build_conditions(conditions)
			return self.sql("DELETE FROM `tab{doctype}` where {conditions}".format(
				doctype=doctype,
				conditions=conditions
			), values, debug=debug)
		else:
			frappe.throw(_('No conditions provided'))

	def get_last_created(self, doctype):
		last_record = self.get_all(doctype, ('creation'), limit=1, order_by='creation desc')
		if last_record:
			return get_datetime(last_record[0].creation)
		else:
			return None

	def clear_table(self, doctype):
		self.sql('truncate `tab{}`'.format(doctype))

	def log_touched_tables(self, query, values=None):
		if values:
			query = frappe.safe_decode(self._cursor.mogrify(query, values))
		if query.strip().lower().split()[0] in ('insert', 'delete', 'update', 'alter'):
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
		fields = ", ".join(["`"+field+"`" for field in fields])

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
	if frappe.flags.enqueue_after_commit and len(frappe.flags.enqueue_after_commit) > 0:
		for job in frappe.flags.enqueue_after_commit:
			q = get_queue(job.get("queue"), is_async=job.get("is_async"))
			q.enqueue_call(execute_job, timeout=job.get("timeout"),
							kwargs=job.get("queue_args"))
		frappe.flags.enqueue_after_commit = []

# Helpers
def _cast_result(doctype, result):
	batch = [ ]

	try:
		for field, value in result:
			df = frappe.get_meta(doctype).get_field(field)
			if df:
				value = cast_fieldtype(df.fieldtype, value)

			batch.append(tuple([field, value]))
	except frappe.exceptions.DoesNotExistError:
		return result

	return tuple(batch)
