# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

# Database Module
# --------------------

from __future__ import unicode_literals
import MySQLdb
import webnotes
import conf

class Database:
	"""
	   Open a database connection with the given parmeters, if use_default is True, use the
	   login details from `conf.py`. This is called by the request handler and is accessible using
	   the `conn` global variable. the `sql` method is also global to run queries
	"""
	def __init__(self, host=None, user=None, password=None, ac_name=None, use_default = 0):
		self.host = host or 'localhost'
		self.user = user or conf.db_name

		if ac_name:
			self.user = self.get_db_login(ac_name) or conf.db_name
		
		if use_default:
			self.user = conf.db_name

		self.in_transaction = 0
		self.transaction_writes = 0
		self.auto_commit_on_many_writes = 0

		self.password = password or webnotes.get_db_password(self.user)
				
		self.connect()
		if self.user != 'root':
			self.use(self.user)
			
	def get_db_login(self, ac_name):
		return ac_name

	def connect(self):
		"""
		      Connect to a database
		"""
		self._conn = MySQLdb.connect(user=self.user, host=self.host, passwd=self.password, use_unicode=True, charset='utf8')
		self._conn.converter[246]=float
		self._cursor = self._conn.cursor()
	
	def use(self, db_name):
		"""
		      `USE` db_name
		"""
		self._conn.select_db(db_name)
		self.cur_db_name = db_name
	
	def check_transaction_status(self, query):
		"""
		      Update *in_transaction* and check if "START TRANSACTION" is not called twice
		"""
		if self.in_transaction and query and query.strip().split()[0].lower() in ['start', 'alter', 'drop', 'create']:
			raise Exception, 'This statement can cause implicit commit'

		if query and query.strip().lower()=='start transaction':
			self.in_transaction = 1
			self.transaction_writes = 0
			
		if query and query.strip().split()[0].lower() in ['commit', 'rollback']:
			self.in_transaction = 0

		if self.in_transaction and query[:6].lower() in ['update', 'insert']:
			self.transaction_writes += 1
			if self.transaction_writes > 10000:
				if self.auto_commit_on_many_writes:
					webnotes.conn.commit()
					webnotes.conn.begin()
				else:
					webnotes.msgprint('A very long query was encountered. If you are trying to import data, please do so using smaller files')
					raise Exception, 'Bad Query!!! Too many writes'
	
	def fetch_as_dict(self, formatted=0, as_utf8=0):
		"""
		      Internal - get results as dictionary
		"""
		result = self._cursor.fetchall()
		ret = []
		for r in result:
			row_dict = webnotes.DictObj({})
			for i in range(len(r)):
				val = self.convert_to_simple_type(r[i], formatted)
				if as_utf8 and type(val) is unicode:
					val = val.encode('utf-8')
				row_dict[self._cursor.description[i][0]] = val
			ret.append(row_dict)
		return ret
	
	def validate_query(self, q):
		cmd = q.strip().lower().split()[0]
		if cmd in ['alter', 'drop', 'truncate'] and webnotes.user.name != 'Administrator':
			webnotes.msgprint('Not allowed to execute query')
			raise Execption

	# ======================================================================================
	
	def sql(self, query, values=(), as_dict = 0, as_list = 0, formatted = 0, 
		debug=0, ignore_ddl=0, as_utf8=0, auto_commit=0):
		"""
		      * Execute a `query`, with given `values`
		      * returns as a dictionary if as_dict = 1
		      * returns as a list of lists (with cleaned up dates) if as_list = 1
		"""
		# in transaction validations
		self.check_transaction_status(query)
		
		# autocommit
		if auto_commit and self.in_transaction: self.commit()
		if auto_commit: self.begin()
			
		# execute
		try:
			if values!=():
				if isinstance(values, dict):
					values = dict(values)
				if debug: webnotes.errprint(query % values)
				self._cursor.execute(query, values)
				
			else:
				if debug: webnotes.errprint(query)
				self._cursor.execute(query)	
		except Exception, e:
			# ignore data definition errors
			if ignore_ddl and e.args[0] in (1146,1054,1091):
				pass
			else:
				raise e

		if auto_commit: self.commit()

		# scrub output if required
		if as_dict:
			return self.fetch_as_dict(formatted, as_utf8)
		elif as_list:
			return self.convert_to_lists(self._cursor.fetchall(), formatted, as_utf8)
		elif as_utf8:
			return self.convert_to_lists(self._cursor.fetchall(), formatted, as_utf8)
		else:
			return self._cursor.fetchall()

		
	def get_description(self):
		"""
		      Get metadata of the last query
		"""
		return self._cursor.description

	# ======================================================================================

	def convert_to_simple_type(self, v, formatted=0):
		import datetime
		from webnotes.utils import formatdate, fmt_money

		# date
		if type(v)==datetime.date:
			v = str(v)
			if formatted:
				v = formatdate(v)
		
		# time	
		elif type(v)==datetime.timedelta:
			h = int(v.seconds/60/60)
			v = str(h) + ':' + str(v.seconds/60 - h*60)
			if v[1]==':': 
				v='0'+v
		
		# datetime
		elif type(v)==datetime.datetime:
			v = str(v)
		
		# long
		elif type(v)==long: 
			v=int(v)
		
		# convert to strings... (if formatted)
		if formatted:
			if type(v)==float:
				v=fmt_money(v)
			if type(v)==int:
				v=str(v)
		
		return v

	# ======================================================================================

	def convert_to_lists(self, res, formatted=0, as_utf8=0):
		"""
		      Convert the given result set to a list of lists (with cleaned up dates and decimals)
		"""
		nres = []
		for r in res:
			nr = []
			for c in r:
				val = self.convert_to_simple_type(c, formatted)
				if as_utf8 and type(val) is unicode:
					val = val.encode('utf-8')
				nr.append(val)
			nres.append(nr)
		return nres
		
	# ======================================================================================

	def convert_to_utf8(self, res, formatted=0):
		"""
		      Convert the given result set to a list of lists and as utf8 (with cleaned up dates and decimals)
		"""
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
					* `fieldname` = %(fieldname)s
			"""
			if "[" in key:
				split_key = key.split("[")
				return "ifnull(`" + split_key[0] + "`, " + split_key[1][:-1] + ") = %(" + key + ")s"
			else:
				return "`" + key + "` = %(" + key + ")s"

		if isinstance(filters, basestring):
			filters = { "name": filters }
		conditions = map(_build_condition, filters)

		return " and ".join(conditions), filters

	def get_value(self, doctype, filters=None, fieldname="name", ignore=None, as_dict=False):
		"""Get a single / multiple value from a record. 
		For Single DocType, let filters be = None"""
		if filters is not None and (filters!=doctype or filters=='DocType'):
			fl = isinstance(fieldname, basestring) and fieldname or "`, `".join(fieldname)
			conditions, filters = self.build_conditions(filters)
			
			try:
				r = self.sql("select `%s` from `tab%s` where %s" % (fl, doctype,
					conditions), filters, as_dict)
			except Exception, e:
				if e.args[0]==1054 and ignore:
					return None
				else:
					raise e

			return r and (len(r[0]) > 1 and r[0] or r[0][0]) or None

		else:
			fieldname = isinstance(fieldname, basestring) and [fieldname] or fieldname

			r = self.sql("select field, value from tabSingles where field in (%s) and \
				doctype=%s" % (', '.join(['%s']*len(fieldname)), '%s'), tuple(fieldname) + (doctype,), as_dict=False)
			if as_dict:
				return r and webnotes.DictObj(r) or None
			else:
				return r and (len(r) > 1 and [i[0] for i in r] or r[0][1]) or None

	def set_value(self, dt, dn, field, val, modified = None):
		from webnotes.utils import now
		if dn and dt!=dn:
			self.sql("update `tab"+dt+"` set `"+field+"`=%s, modified=%s where name=%s", (val, modified or now(), dn))
		else:
			if self.sql("select value from tabSingles where field=%s and doctype=%s", (field, dt)):
				self.sql("update tabSingles set value=%s where field=%s and doctype=%s", (val, field, dt))
			else:
				self.sql("insert into tabSingles(doctype, field, value) values (%s, %s, %s)", (dt, field, val))
				
	def set(self, doc, field, val):
		from webnotes.utils import now
		doc.modified = now()
		self.set_value(doc.doctype, doc.name, field, val, doc.modified)
		doc.fields[field] = val

	# ======================================================================================

	def set_global(self, key, val, user='__global'):
		res = self.sql('select defkey from `tabDefaultValue` where defkey=%s and parent=%s', (key, user))
		if res:
			self.sql('update `tabDefaultValue` set defvalue=%s where parent=%s and defkey=%s', (str(val), user, key))
		else:
			self.sql('insert into `tabDefaultValue` (name, defkey, defvalue, parent) values (%s,%s,%s,%s)', (user+'_'+key, key, str(val), user))

	def get_global(self, key, user='__global'):
		g = self.sql("select defvalue from tabDefaultValue where defkey=%s and parent=%s", (key, user))
		return g and g[0][0] or None

	# ======================================================================================

	def set_default(self, key, val, parent="Control Panel"):
		"""set control panel default (tabDefaultVal)"""

		if self.sql("""select defkey from `tabDefaultValue` where 
			defkey=%s and parent=%s """, (key, parent)):
			
			# update
			self.sql("""update `tabDefaultValue` set defvalue=%s 
				where parent=%s and defkey=%s""", (val, parent, key))
		else:
			from webnotes.model.doc import Document
			d = Document('DefaultValue')
			d.parent = parent
			d.parenttype = 'Control Panel' # does not matter
			d.parentfield = 'system_defaults'
			d.defkey = key
			d.defvalue = val
			d.save(1)
	
	def get_default(self, key):
		"""get default value"""
		ret = self.sql("""select defvalue from \
			tabDefaultValue where defkey=%s""", key)
		return ret and ret[0][0] or None
		
	def get_defaults(self, key=None):
		"""get all defaults"""
		if key:
			return self.get_default(key)
		else:
			res = self.sql("""select defkey, defvalue from `tabDefaultValue` 
				where parent = "Control Panel" """)
			d = {}
			for rec in res: 
				d[rec[0]] = rec[1] or ''
			return d		

	def begin(self):
		if not self.in_transaction:
			self.sql("start transaction")
	
	def commit(self):
		self.sql("commit")


	def rollback(self):
		self.sql("ROLLBACK")

	# ======================================================================================

	def field_exists(self, dt, fn):
		"""
		      Returns True if `fn` exists in `DocType` `dt`
		"""	
		return self.sql("select name from tabDocField where fieldname=%s and parent=%s", (dt, fn))

	def exists(self, dt, dn=None):
		"""
		      Returns true if the record exists
		"""	
		if isinstance(dt, basestring):
			try:
				return self.sql('select name from `tab%s` where name=%s' % (dt, '%s'), dn)
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

	# ======================================================================================
	def close(self):
		"""
		      Close my connection
		"""
		if self._conn:
			self._cursor.close()
			self._conn.close()
			self._cursor = None
			self._conn = None
