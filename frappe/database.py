# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# Database Module
# --------------------

from __future__ import unicode_literals
import MySQLdb
import warnings
import datetime
import frappe
import frappe.model.meta
from frappe.utils import now, get_datetime
from frappe import _

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

	def get_db_login(self, ac_name):
		return ac_name

	def connect(self):
		"""
		      Connect to a database
		"""
		warnings.filterwarnings('ignore', category=MySQLdb.Warning)
		self._conn = MySQLdb.connect(user=self.user, host=self.host, passwd=self.password,
			use_unicode=True, charset='utf8')
		self._conn.converter[246]=float
		self._conn.converter[12]=get_datetime

		self._cursor = self._conn.cursor()
		if self.user != 'root':
			self.use(self.user)
		frappe.local.rollback_observers = []

	def use(self, db_name):
		"""
		      `USE` db_name
		"""
		self._conn.select_db(db_name)
		self.cur_db_name = db_name

	def validate_query(self, q):
		cmd = q.strip().lower().split()[0]
		if cmd in ['alter', 'drop', 'truncate'] and frappe.user.name != 'Administrator':
			frappe.throw(_("Not permitted"), frappe.PermissionError)

	def sql(self, query, values=(), as_dict = 0, as_list = 0, formatted = 0,
		debug=0, ignore_ddl=0, as_utf8=0, auto_commit=0, update=None):
		"""
		      * Execute a `query`, with given `values`
		      * returns as a dictionary if as_dict = 1
		      * returns as a list of lists (with cleaned up dates) if as_list = 1
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
		return [r[0] for r in self.sql(query, values, debug=debug)]

	def sql_ddl(self, query, values=()):
		self.commit()
		self.sql(query)

	def check_transaction_status(self, query):
		if self.transaction_writes and \
			query and query.strip().split()[0].lower() in ['start', 'alter', 'drop', 'create', "begin"]:
			raise Exception, 'This statement can cause implicit commit'

		if query and query.strip().lower() in ('commit', 'rollback'):
			self.transaction_writes = 0

		if query[:6].lower() in ['update', 'insert']:
			self.transaction_writes += 1
			if self.transaction_writes > 10000:
				if self.auto_commit_on_many_writes:
					frappe.db.commit()
				else:
					frappe.throw(_("Too many writes in one request. Please send smaller requests"), frappe.ValidationError)

	def fetch_as_dict(self, formatted=0, as_utf8=0):
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
		if result and result[0]:
			for v in result[0]:
				if isinstance(v, (datetime.date, datetime.timedelta, datetime.datetime, long)):
					return True
				if formatted and isinstance(v, (int, float)):
					return True

		return False

	def get_description(self):
		return self._cursor.description

	def convert_to_simple_type(self, v, formatted=0):
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
		def _build_condition(key):
			"""
				filter's key is passed by map function
				build conditions like:
					* ifnull(`fieldname`, default_value) = %(fieldname)s
					* `fieldname` [=, !=, >, >=, <, <=] %(fieldname)s
			"""
			_operator = "="
			value = filters.get(key)
			if isinstance(value, (list, tuple)):
				_operator = value[0]
				filters[key] = value[1]

			if _operator not in ["=", "!=", ">", ">=", "<", "<=", "like"]:
				_operator = "="

			if "[" in key:
				split_key = key.split("[")
				return "ifnull(`" + split_key[0] + "`, " + split_key[1][:-1] + ") " \
					+ _operator + " %(" + key + ")s"
			else:
				return "`" + key + "` " + _operator + " %(" + key + ")s"

		if isinstance(filters, basestring):
			filters = { "name": filters }
		conditions = map(_build_condition, filters)

		return " and ".join(conditions), filters

	def get(self, doctype, filters=None, as_dict=True):
		return self.get_value(doctype, filters, "*", as_dict=as_dict)

	def get_value(self, doctype, filters=None, fieldname="name", ignore=None, as_dict=False, debug=False):
		"""Get a single / multiple value from a record.
		For Single DocType, let filters be = None"""

		ret = self.get_values(doctype, filters, fieldname, ignore, as_dict, debug)

		return ((len(ret[0]) > 1 or as_dict) and ret[0] or ret[0][0]) if ret else None

	def get_values(self, doctype, filters=None, fieldname="name", ignore=None, as_dict=False, debug=False, order_by=None, update=None):
		if isinstance(filters, list):
			return self.get_value_for_many_names(doctype, filters, fieldname, debug=debug)

		fields = fieldname
		if fieldname!="*":
			if isinstance(fieldname, basestring):
				fields = [fieldname]
			else:
				fields = fieldname

		if (filters is not None) and (filters!=doctype or doctype=="DocType"):
			try:
				return self.get_values_from_table(fields, filters, doctype, as_dict, debug, order_by, update)
			except Exception, e:
				if ignore and e.args[0] in (1146, 1054):
					# table or column not found, return None
					return None
				elif (not ignore) and e.args[0]==1146:
					# table not found, look in singles
					pass
				else:
					raise

		return self.get_values_from_single(fields, filters, doctype, as_dict, debug, update)

	def get_values_from_single(self, fields, filters, doctype, as_dict=False, debug=False, update=None):
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
		return frappe._dict(self.sql("""select field, value from
			tabSingles where doctype=%s""", doctype))


	def get_values_from_table(self, fields, filters, doctype, as_dict, debug, order_by=None, update=None):
		fl = []
		if isinstance(fields, (list, tuple)):
			for f in fields:
				if "(" in f: # function
					fl.append(f)
				else:
					fl.append("`" + f + "`")
			fl = ", ".join(fields)
		else:
			fl = fields
			if fields=="*":
				as_dict = True

		conditions, filters = self.build_conditions(filters)

		order_by = ("order by " + order_by) if order_by else ""

		r = self.sql("select %s from `tab%s` where %s %s" % (fl, doctype,
			conditions, order_by), filters, as_dict=as_dict, debug=debug, update=update)

		return r

	def get_value_for_many_names(self, doctype, names, field, debug=False):
		names = filter(None, names)

		if names:
			return dict(self.sql("select name, `%s` from `tab%s` where name in (%s)" \
				% (field, doctype, ", ".join(["%s"]*len(names))), names, debug=debug))
		else:
			return {}

	def set_value(self, dt, dn, field, val, modified=None, modified_by=None):
		if not modified:
			modified = now()
		if not modified_by:
			modified_by = frappe.session.user

		if dn and dt!=dn:
			self.sql("""update `tab%s` set `%s`=%s, modified=%s, modified_by=%s
				where name=%s""" % (dt, field, "%s", "%s", "%s", "%s"),
				(val, modified, modified_by, dn))
		else:
			if self.sql("select value from tabSingles where field=%s and doctype=%s", (field, dt)):
				self.sql("""update tabSingles set value=%s where field=%s and doctype=%s""",
					(val, field, dt))
			else:
				self.sql("""insert into tabSingles(doctype, field, value)
					values (%s, %s, %s)""", (dt, field, val))

			if field not in ("modified", "modified_by"):
				self.set_value(dt, dn, "modified", modified)
				self.set_value(dt, dn, "modified_by", modified_by)

	def set(self, doc, field, val):
		doc.db_set(field, val)

	def touch(self, doctype, docname):
		from frappe.utils import now
		modified = now()
		frappe.db.sql("""update `tab{doctype}` set `modified`=%s
			where name=%s""".format(doctype=doctype), (modified, docname))
		return modified

	def set_global(self, key, val, user='__global'):
		self.set_default(key, val, user)

	def get_global(self, key, user='__global'):
		return self.get_default(key, user)

	def set_default(self, key, val, parent="__default", parenttype=None):
		import frappe.defaults
		frappe.defaults.set_default(key, val, parent, parenttype)

	def add_default(self, key, val, parent="__default", parenttype=None):
		import frappe.defaults
		frappe.defaults.add_default(key, val, parent, parenttype)

	def get_default(self, key, parent="__default"):
		"""get default value"""
		import frappe.defaults
		d = frappe.defaults.get_defaults(parent).get(key)
		return isinstance(d, list) and d[0] or d

	def get_defaults_as_list(self, key, parent="__default"):
		import frappe.defaults
		d = frappe.defaults.get_default(key, parent)
		return isinstance(d, basestring) and [d] or d

	def get_defaults(self, key=None, parent="__default"):
		"""get all defaults"""
		import frappe.defaults
		if key:
			return frappe.defaults.get_defaults(parent).get(key)
		else:
			return frappe.defaults.get_defaults(parent)

	def begin(self):
		return # not required

	def commit(self):
		self.sql("commit")
		frappe.local.rollback_observers = []

	def rollback(self):
		self.sql("rollback")
		for obj in frappe.local.rollback_observers:
			if hasattr(obj, "on_rollback"):
				obj.on_rollback()
		frappe.local.rollback_observers = []

	def field_exists(self, dt, fn):
		return self.sql("select name from tabDocField where fieldname=%s and parent=%s", (dt, fn))

	def table_exists(self, tablename):
		return tablename in [d[0] for d in self.sql("show tables")]

	def exists(self, dt, dn=None):
		if isinstance(dt, basestring):
			if dt!="DocType" and dt==dn:
				return True # single always exists (!)
			try:
				return self.sql('select name from `tab%s` where name=%s' % (dt, '%s'), (dn,))
			except:
				return None
		elif isinstance(dt, dict) and dt.get('doctype'):
			try:
				conditions = []
				for d in dt:
					if d == 'doctype': continue
					conditions.append('`%s` = "%s"' % (d, dt[d].replace('"', '\"')))
				return self.sql('select name from `tab%s` where %s' % \
						(dt['doctype'], " and ".join(conditions)))
			except:
				return None

	def count(self, dt, filters=None, debug=False):
		if filters:
			conditions, filters = self.build_conditions(filters)
			return frappe.db.sql("""select count(*)
				from `tab%s` where %s""" % (dt, conditions), filters, debug=debug)[0][0]
		else:
			return frappe.db.sql("""select count(*)
				from `tab%s`""" % (dt,))[0][0]


	def get_creation_count(self, doctype, minutes):
		"""get count of records created in the last x minutes"""
		from frappe.utils import now_datetime
		from dateutil.relativedelta import relativedelta

		return frappe.db.sql("""select count(name) from `tab{doctype}`
			where creation >= %s""".format(doctype=doctype),
			now_datetime() - relativedelta(minutes=minutes))[0][0]

	def get_table_columns(self, doctype):
		return [r[0] for r in self.sql("DESC `tab%s`" % doctype)]

	def add_index(self, doctype, fields, index_name=None):
		if not index_name:
			index_name = "_".join(fields) + "_index"
		if not frappe.db.sql("""show index from `tab%s` where Key_name="%s" """ % (doctype, index_name)):
			frappe.db.commit()
			frappe.db.sql("""alter table `tab%s`
				add index %s(%s)""" % (doctype, index_name, ", ".join(fields)))

	def close(self):
		if self._conn:
			self._cursor.close()
			self._conn.close()
			self._cursor = None
			self._conn = None
