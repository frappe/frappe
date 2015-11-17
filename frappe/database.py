# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# Database Module
# --------------------

from __future__ import unicode_literals
import MySQLdb
from MySQLdb.times import DateTimeDeltaType
from markdown2 import UnicodeWithAttrs
import warnings
import datetime
import frappe
import frappe.defaults
import re
import frappe.model.meta
from frappe.utils import now, get_datetime, cstr
from frappe import _
from types import StringType, UnicodeType

class Database:
	"""
	   Open a database connection with the given parmeters, if use_default is True, use the
	   login details from `conf.py`. This is called by the request handler and is accessible using
	   the `db` global variable. the `sql` method is also global to run queries
	"""
	def __init__(self, host=None, user=None, password=None, ac_name=None, use_default = 0):
		self.host = host or frappe.conf.db_host or 'localhost'
		self.user = user or frappe.conf.db_name
		self._conn = None

		if ac_name:
			self.user = self.get_db_login(ac_name) or frappe.conf.db_name

		if use_default:
			self.user = frappe.conf.db_name

		self.transaction_writes = 0
		self.auto_commit_on_many_writes = 0

		self.password = password or frappe.conf.db_password
		self.value_cache = {}

	def get_db_login(self, ac_name):
		return ac_name

	def connect(self):
		"""Connects to a database as set in `site_config.json`."""
		warnings.filterwarnings('ignore', category=MySQLdb.Warning)
		self._conn = MySQLdb.connect(user=self.user, host=self.host, passwd=self.password,
			use_unicode=True, charset='utf8')
		self._conn.converter[246]=float
		self._conn.converter[12]=get_datetime
		self._conn.encoders[UnicodeWithAttrs] = self._conn.encoders[UnicodeType]
		self._conn.encoders[DateTimeDeltaType] = self._conn.encoders[StringType]

		MYSQL_OPTION_MULTI_STATEMENTS_OFF = 1
		self._conn.set_server_option(MYSQL_OPTION_MULTI_STATEMENTS_OFF)

		self._cursor = self._conn.cursor()
		if self.user != 'root':
			self.use(self.user)
		frappe.local.rollback_observers = []

	def use(self, db_name):
		"""`USE` db_name."""
		self._conn.select_db(db_name)
		self.cur_db_name = db_name

	def validate_query(self, q):
		"""Throw exception for dangerous queries: `ALTER`, `DROP`, `TRUNCATE` if not `Administrator`."""
		cmd = q.strip().lower().split()[0]
		if cmd in ['alter', 'drop', 'truncate'] and frappe.session.user != 'Administrator':
			frappe.throw(_("Not permitted"), frappe.PermissionError)

	def sql(self, query, values=(), as_dict = 0, as_list = 0, formatted = 0,
		debug=0, ignore_ddl=0, as_utf8=0, auto_commit=0, update=None):
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
		if not self._conn:
			self.connect()

		# in transaction validations
		self.check_transaction_status(query)

		# autocommit
		if auto_commit: self.commit()

		# execute
		try:
			if values!=():
				if isinstance(values, dict):
					values = dict(values)

				# MySQL-python==1.2.5 hack!
				if not isinstance(values, (dict, tuple, list)):
					values = (values,)

				if debug:
					try:
						self.explain_query(query, values)
						frappe.errprint(query % values)
					except TypeError:
						frappe.errprint([query, values])
				if (frappe.conf.get("logging") or False)==2:
					frappe.log("<<<< query")
					frappe.log(query)
					frappe.log("with values:")
					frappe.log(values)
					frappe.log(">>>>")
				self._cursor.execute(query, values)

			else:
				if debug:
					self.explain_query(query)
					frappe.errprint(query)
				if (frappe.conf.get("logging") or False)==2:
					frappe.log("<<<< query")
					frappe.log(query)
					frappe.log(">>>>")

				self._cursor.execute(query)
		except Exception, e:
			# ignore data definition errors
			if ignore_ddl and e.args[0] in (1146,1054,1091):
				pass
			else:
				raise

		if auto_commit: self.commit()

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
		except:
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
			raise Exception, 'This statement can cause implicit commit'

		if query and query.strip().lower() in ('commit', 'rollback'):
			self.transaction_writes = 0

		if query[:6].lower() in ('update', 'insert', 'delete'):
			self.transaction_writes += 1
			if self.transaction_writes > 200000:
				if self.auto_commit_on_many_writes:
					frappe.db.commit()
				else:
					frappe.throw(_("Too many writes in one request. Please send smaller requests"), frappe.ValidationError)

	def fetch_as_dict(self, formatted=0, as_utf8=0):
		"""Internal. Converts results to dict."""
		result = self._cursor.fetchall()
		ret = []
		needs_formatting = self.needs_formatting(result, formatted)

		for r in result:
			row_dict = frappe._dict({})
			for i in range(len(r)):
				if needs_formatting:
					val = self.convert_to_simple_type(r[i], formatted)
				else:
					val = r[i]

				if as_utf8 and type(val) is unicode:
					val = val.encode('utf-8')
				row_dict[self._cursor.description[i][0]] = val
			ret.append(row_dict)
		return ret

	def needs_formatting(self, result, formatted):
		"""Returns true if the first row in the result has a Date, Datetime, Long Int."""
		if result and result[0]:
			for v in result[0]:
				if isinstance(v, (datetime.date, datetime.timedelta, datetime.datetime, long)):
					return True
				if formatted and isinstance(v, (int, float)):
					return True

		return False

	def get_description(self):
		"""Returns result metadata."""
		return self._cursor.description

	def convert_to_simple_type(self, v, formatted=0):
		"""Format date, time, longint values."""
		return v

		from frappe.utils import formatdate, fmt_money

		if isinstance(v, (datetime.date, datetime.timedelta, datetime.datetime, long)):
			if isinstance(v, datetime.date):
				v = unicode(v)
				if formatted:
					v = formatdate(v)

			# time
			elif isinstance(v, (datetime.timedelta, datetime.datetime)):
				v = unicode(v)

			# long
			elif isinstance(v, long):
				v=int(v)

		# convert to strings... (if formatted)
		if formatted:
			if isinstance(v, float):
				v=fmt_money(v)
			elif isinstance(v, int):
				v = unicode(v)

		return v

	def convert_to_lists(self, res, formatted=0, as_utf8=0):
		"""Convert tuple output to lists (internal)."""
		nres = []
		needs_formatting = self.needs_formatting(res, formatted)
		for r in res:
			nr = []
			for c in r:
				if needs_formatting:
					val = self.convert_to_simple_type(c, formatted)
				else:
					val = c
				if as_utf8 and type(val) is unicode:
					val = val.encode('utf-8')
				nr.append(val)
			nres.append(nr)
		return nres

	def convert_to_utf8(self, res, formatted=0):
		"""Encode result as UTF-8."""
		nres = []
		for r in res:
			nr = []
			for c in r:
				if type(c) is unicode:
					c = c.encode('utf-8')
					nr.append(self.convert_to_simple_type(c, formatted))
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
				# value is a tuble like ("!=", 0)
				_operator = value[0]
				values[key] = value[1]
				if isinstance(value[1], (tuple, list)):
					# value is a list in tuple ("in", ("A", "B"))
					inner_list = []
					for i, v in enumerate(value[1]):
						inner_key = "{0}_{1}".format(key, i)
						values[inner_key] = v
						inner_list.append("%({0})s".format(inner_key))

					_rhs = " ({0})".format(", ".join(inner_list))
					del values[key]

			if _operator not in ["=", "!=", ">", ">=", "<", "<=", "like", "in", "not in", "not like"]:
				_operator = "="

			if "[" in key:
				split_key = key.split("[")
				condition = "ifnull(`" + split_key[0] + "`, " + split_key[1][:-1] + ") " \
					+ _operator + _rhs
			else:
				condition = "`" + key + "` " + _operator + _rhs

			conditions.append(condition)

		if isinstance(filters, basestring):
			filters = { "name": filters }

		for f in filters:
			_build_condition(f)

		return " and ".join(conditions), values

	def get(self, doctype, filters=None, as_dict=True, cache=False):
		"""Returns `get_value` with fieldname='*'"""
		return self.get_value(doctype, filters, "*", as_dict=as_dict, cache=cache)

	def get_value(self, doctype, filters=None, fieldname="name", ignore=None, as_dict=False, debug=False, cache=False):
		"""Returns a document property or list of properties.

		:param doctype: DocType name.
		:param filters: Filters like `{"x":"y"}` or name of the document. `None` if Single DocType.
		:param fieldname: Column name.
		:param ignore: Don't raise exception if table, column is missing.
		:param as_dict: Return values as dict.
		:param debug: Print query in error log.

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

		ret = self.get_values(doctype, filters, fieldname, ignore, as_dict, debug, cache=cache)

		return ((len(ret[0]) > 1 or as_dict) and ret[0] or ret[0][0]) if ret else None

	def get_values(self, doctype, filters=None, fieldname="name", ignore=None, as_dict=False,
		debug=False, order_by=None, update=None, cache=False):
		"""Returns multiple document properties.

		:param doctype: DocType name.
		:param filters: Filters like `{"x":"y"}` or name of the document.
		:param fieldname: Column name.
		:param ignore: Don't raise exception if table, column is missing.
		:param as_dict: Return values as dict.
		:param debug: Print query in error log.

		Example:

			# return first customer starting with a
			customers = frappe.db.get_values("Customer", {"name": ("like a%")})

			# return last login of **User** `test@example.com`
			user = frappe.db.get_values("User", "test@example.com", "*")[0]
		"""
		out = None
		if cache and isinstance(filters, basestring) and \
			(doctype, filters, fieldname) in self.value_cache:
			return self.value_cache[(doctype, filters, fieldname)]

		if isinstance(filters, list):
			out = self._get_value_for_many_names(doctype, filters, fieldname, debug=debug)

		else:
			fields = fieldname
			if fieldname!="*":
				if isinstance(fieldname, basestring):
					fields = [fieldname]
				else:
					fields = fieldname

			if (filters is not None) and (filters!=doctype or doctype=="DocType"):
				try:
					out = self._get_values_from_table(fields, filters, doctype, as_dict, debug, order_by, update)
				except Exception, e:
					if ignore and e.args[0] in (1146, 1054):
						# table or column not found, return None
						out = None
					elif (not ignore) and e.args[0]==1146:
						# table not found, look in singles
						out = self.get_values_from_single(fields, filters, doctype, as_dict, debug, update)
					else:
						raise
			else:
				out = self.get_values_from_single(fields, filters, doctype, as_dict, debug, update)

		if cache and isinstance(filters, basestring):
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
				return [map(lambda d: values.get(d), fields)]

		else:
			r = self.sql("""select field, value
				from tabSingles where field in (%s) and doctype=%s""" \
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

	def get_singles_dict(self, doctype):
		"""Get Single DocType as dict."""
		return frappe._dict(self.sql("""select field, value from
			tabSingles where doctype=%s""", doctype))

	def get_all(self, *args, **kwargs):
		return frappe.get_all(*args, **kwargs)

	def get_list(self, *args, **kwargs):
		return frappe.get_list(*args, **kwargs)

	def get_single_value(self, doctype, fieldname, cache=False):
		"""Get property of Single DocType. Cache locally by default"""
		value = self.value_cache.setdefault(doctype, {}).get(fieldname)
		if value:
			return value

		val = self.sql("""select value from
			tabSingles where doctype=%s and field=%s""", (doctype, fieldname))
		val = val[0][0] if val else None

		if val=="0" or val=="1":
			# check type
			val = int(val)

		self.value_cache[doctype][fieldname] = val

		return val

	def get_singles_value(self, *args, **kwargs):
		"""Alias for get_single_value"""
		return self.get_single_value(*args, **kwargs)

	def _get_values_from_table(self, fields, filters, doctype, as_dict, debug, order_by=None, update=None):
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

		r = self.sql("select {0} from `tab{1}` where {2} {3}".format(fl, doctype,
			conditions, order_by), values, as_dict=as_dict, debug=debug, update=update)

		return r

	def _get_value_for_many_names(self, doctype, names, field, debug=False):
		names = filter(None, names)

		if names:
			return dict(self.sql("select name, `%s` from `tab%s` where name in (%s)" \
				% (field, doctype, ", ".join(["%s"]*len(names))), names, debug=debug))
		else:
			return {}

	def update(self, *args, **kwargs):
		"""Update multiple values. Alias for `set_value`."""
		return self.set_value(*args, **kwargs)

	def set_value(self, dt, dn, field, val, modified=None, modified_by=None,
		update_modified=True, debug=False):
		"""Set a single value in the database, do not call the ORM triggers
		but update the modified timestamp (unless specified not to).

		**Warning:** this function will not call Document events and should be avoided in normal cases.

		:param dt: DocType name.
		:param dn: Document name.
		:param field: Property / field name.
		:param value: Value to be updated.
		:param modified: Use this as the `modified` timestamp.
		:param modified_by: Set this user as `modified_by`.
		:param update_modified: default True. Set as false, if you don't want to update the timestamp.
		:param debug: Print the query in the developer / js console.
		"""
		if not modified:
			modified = now()
		if not modified_by:
			modified_by = frappe.session.user

		if dn and dt!=dn:
			conditions, values = self.build_conditions(dn)

			values.update({"val": val, "modified": modified, "modified_by": modified_by})

			if update_modified:
				self.sql("""update `tab{0}` set `{1}`=%(val)s, modified=%(modified)s, modified_by=%(modified_by)s where
					{2}""".format(dt, field, conditions), values, debug=debug)
			else:
				self.sql("""update `tab{0}` set `{1}`=%(val)s where
					{2}""".format(dt, field, conditions), values, debug=debug)


		else:
			self.sql("delete from tabSingles where field=%s and doctype=%s", (field, dt))
			self.sql("insert into tabSingles(doctype, field, value) values (%s, %s, %s)",
				(dt, field, val), debug=debug)

			if update_modified and (field not in ("modified", "modified_by")):
				self.set_value(dt, dn, "modified", modified)
				self.set_value(dt, dn, "modified_by", modified_by)


		if dt in self.value_cache:
			del self.value_cache[dt]

	def set(self, doc, field, val):
		"""Set value in document. **Avoid**"""
		doc.db_set(field, val)

	def touch(self, doctype, docname):
		"""Update the modified timestamp of this document."""
		from frappe.utils import now
		modified = now()
		frappe.db.sql("""update `tab{doctype}` set `modified`=%s
			where name=%s""".format(doctype=doctype), (modified, docname))
		return modified

	def set_temp(self, value):
		"""Set a temperory value and return a key."""
		key = frappe.generate_hash()
		frappe.cache().hset("temp", key, value)
		return key

	def get_temp(self, key):
		"""Return the temperory value and delete it."""
		return frappe.cache().hget("temp", key)

	def set_global(self, key, val, user='__global'):
		"""Save a global key value. Global values will be automatically set if they match fieldname."""
		self.set_default(key, val, user)

	def get_global(self, key, user='__global'):
		"""Returns a global key value."""
		return self.get_default(key, user)

	def set_default(self, key, val, parent="__default", parenttype=None):
		"""Sets a global / user default value."""
		frappe.defaults.set_default(key, val, parent, parenttype)

	def add_default(self, key, val, parent="__default", parenttype=None):
		"""Append a default value for a key, there can be multiple default values for a particular key."""
		frappe.defaults.add_default(key, val, parent, parenttype)

	def get_default(self, key, parent="__default"):
		"""Returns default value as a list if multiple or single"""
		d = frappe.defaults.get_defaults(parent).get(key)
		return isinstance(d, list) and d[0] or d

	def get_defaults_as_list(self, key, parent="__default"):
		"""Returns default values as a list."""
		d = frappe.defaults.get_default(key, parent)
		return isinstance(d, basestring) and [d] or d

	def get_defaults(self, key=None, parent="__default"):
		"""Get all defaults"""
		if key:
			return frappe.defaults.get_defaults(parent).get(key)
		else:
			return frappe.defaults.get_defaults(parent)

	def begin(self):
		pass
		#self.sql("start transaction")

	def commit(self):
		"""Commit current transaction. Calls SQL `COMMIT`."""
		self.sql("commit")
		frappe.local.rollback_observers = []

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
		return self.sql("select name from tabDocField where fieldname=%s and parent=%s", (dt, fn))

	def table_exists(self, tablename):
		"""Returns True if table exists."""
		return ("tab" + tablename) in self.get_tables()

	def get_tables(self):
		return [d[0] for d in self.sql("show tables")]

	def a_row_exists(self, doctype):
		"""Returns True if atleast one row exists."""
		return self.sql("select name from `tab{doctype}` limit 1".format(doctype=doctype))

	def exists(self, dt, dn=None):
		"""Returns true if document exists.

		:param dt: DocType name.
		:param dn: Document name or filter dict."""
		if isinstance(dt, basestring):
			if dt!="DocType" and dt==dn:
				return True # single always exists (!)
			try:
				return self.get_value(dt, dn, "name")
			except:
				return None
		elif isinstance(dt, dict) and dt.get('doctype'):
			try:
				conditions = []
				for d in dt:
					if d == 'doctype': continue
					conditions.append('`%s` = "%s"' % (d, cstr(dt[d]).replace('"', '\"')))
				return self.sql('select name from `tab%s` where %s' % \
						(dt['doctype'], " and ".join(conditions)))
			except:
				return None

	def count(self, dt, filters=None, debug=False):
		"""Returns `COUNT(*)` for given DocType and filters."""
		if filters:
			conditions, filters = self.build_conditions(filters)
			return frappe.db.sql("""select count(*)
				from `tab%s` where %s""" % (dt, conditions), filters, debug=debug)[0][0]
		else:
			return frappe.db.sql("""select count(*)
				from `tab%s`""" % (dt,))[0][0]


	def get_creation_count(self, doctype, minutes):
		"""Get count of records created in the last x minutes"""
		from frappe.utils import now_datetime
		from dateutil.relativedelta import relativedelta

		return frappe.db.sql("""select count(name) from `tab{doctype}`
			where creation >= %s""".format(doctype=doctype),
			now_datetime() - relativedelta(minutes=minutes))[0][0]

	def get_table_columns(self, doctype):
		"""Returns list of column names from given doctype."""
		return [r[0] for r in self.sql("DESC `tab%s`" % doctype)]

	def has_column(self, doctype, column):
		"""Returns True if column exists in database."""
		return column in self.get_table_columns(doctype)

	def add_index(self, doctype, fields, index_name=None):
		"""Creates an index with given fields if not already created.
		Index name will be `fieldname1_fieldname2_index`"""
		if not index_name:
			index_name = "_".join(fields) + "_index"

			# remove index length if present e.g. (10) from index name
			index_name = re.sub(r"\s*\([^)]+\)\s*", r"", index_name)

		if not frappe.db.sql("""show index from `tab%s` where Key_name="%s" """ % (doctype, index_name)):
			frappe.db.commit()
			frappe.db.sql("""alter table `tab%s`
				add index `%s`(%s)""" % (doctype, index_name, ", ".join(fields)))

	def add_unique(self, doctype, fields, constraint_name=None):
		if isinstance(fields, basestring):
			fields = [fields]
		if not constraint_name:
			constraint_name = "unique_" + "_".join(fields)

		if not frappe.db.sql("""select CONSTRAINT_NAME from information_schema.TABLE_CONSTRAINTS
			where table_name=%s and constraint_type='UNIQUE' and CONSTRAINT_NAME=%s""",
			('tab' + doctype, constraint_name)):
				frappe.db.commit()
				frappe.db.sql("""alter table `tab%s`
					add unique `%s`(%s)""" % (doctype, constraint_name, ", ".join(fields)))

	def close(self):
		"""Close database connection."""
		if self._conn:
			self._cursor.close()
			self._conn.close()
			self._cursor = None
			self._conn = None

	def escape(self, s):
		"""Excape quotes and percent in given string."""
		if isinstance(s, unicode):
			s = (s or "").encode("utf-8")
		return unicode(MySQLdb.escape_string(s), "utf-8").replace("%","%%").replace("`", "\\`")
