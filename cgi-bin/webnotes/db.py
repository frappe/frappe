# Database Module
# --------------------

import MySQLdb
from webnotes import defs
import webnotes

class Database:
	"""
	   Open a database connection with the given parmeters, if use_default is True, use the
	   login details from `defs.py`. This is called by the request handler and is accessible using
	   the `conn` global variable. the `sql` method is also global to run queries
	"""
	def __init__(self, host=None, user=None, password=None, ac_name=None, use_default = 0):
		self.host = host or 'localhost'
		self.user = user or getattr(defs, 'default_db_name', '')

		# password can be empty string
		self.password = password==None and getattr(defs, 'db_password', '') or password

		if ac_name:
			self.user = self.get_db_login(ac_name) or defs.default_db_name
		
		if use_default:
			self.user = defs.default_db_name

		self.is_testing = 0
		self.in_transaction = 0
		self.transaction_writes = 0
		self.testing_tables = []
		
		self.connect()
		if self.user != 'root':
			self.use(self.user)
		
		if webnotes.logger:
			webnotes.logger.debug('Database object initialized for:%s',self.user)

	def get_db_login(self, ac_name):
		return getattr(defs,'db_name_map').get(ac_name, getattr(defs,'default_db_name'))

	def connect(self):
		"""
		      Connect to a database
		"""
		self._conn = MySQLdb.connect(user=self.user, host=self.host, passwd=self.password)
		try:
			self._conn.set_character_set('utf8')
		except:
			pass

		self._cursor = self._conn.cursor()
		
		return self._cursor
	
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
			if self.transaction_writes > 5000:
				webnotes.msgprint('A very long query was encountered. If you are trying to import data, please do so using smaller files')
				raise Exception, 'Bad Query!!! Too many writes'
	
	def fetch_as_dict(self, formatted=0):
		"""
		      Internal - get results as dictionary
		"""
		result = self._cursor.fetchall()
		ret = []
		for r in result:
			dict = {}
			for i in range(len(r)):
				dict[self._cursor.description[i][0]] = self.convert_to_simple_type(r[i], formatted)
			ret.append(dict)
		return ret
	
	def validate_query(self, q):
		cmd = q.strip().lower().split()[0]
		if cmd in ['alter', 'drop', 'truncate'] and webnotes.user.name != 'Administrator':
			webnotes.msgprint('Not allowed to execute query')
			raise Execption

	# ======================================================================================
	
	def sql(self, query, values=(), as_dict = 0, as_list = 0, formatted = 0, ignore_no_table = 1, debug=0):
		"""
		      * Execute a `query`, with given `values`
		      * returns as a dictionary if as_dict = 1
		      * returns as a list of lists (with cleaned up dates and decimals) if as_list = 1
		"""			
		# in transaction validations
		self.check_transaction_status(query)
		
		if getattr(defs,'multi_tenant',None):
			query = self.add_multi_tenant_condition(query)
			
		# execute
		if values!=():
			self._cursor.execute(query, values)
			if debug: webnotes.msgprint(query % values)
				
		else:
			self._cursor.execute(query)	
			if debug: webnotes.msgprint(query)

		# scrub output if required
		if as_dict:
			return self.fetch_as_dict(formatted)
		elif as_list:
			return self.convert_to_lists(self._cursor.fetchall(), formatted)
		else:
			return self._cursor.fetchall()

	# add condition for tenant id
	# ======================================================================================
	def add_multi_tenant_condition(query):
		import webnotes.multi_tenant
		return webnotes.multi_tenant.query_parser.add_condition(query)
		
	# ======================================================================================

	def get_description(self):
		"""
		      Get metadata of the last query
		"""
		return self._cursor.description

	# ======================================================================================

	def convert_to_simple_type(self, v, formatted=0):
		try: import decimal # for decimal Python 2.5 onwards
		except: pass
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

		# decimal
		try:
			if type(v)==decimal.Decimal: 
				v=float(v)
		except: pass
		
		# convert to strings... (if formatted)
		if formatted:
			if type(v)==float:
				v=fmt_money(v)
			if type(v)==int:
				v=str(v)
		
		return v

	# ======================================================================================

	def convert_to_lists(self, res, formatted=0):
		"""
		      Convert the given result set to a list of lists (with cleaned up dates and decimals)
		"""
		nres = []
		for r in res:
			nr = []
			for c in r:
				nr.append(self.convert_to_simple_type(c, formatted))
			nres.append(nr)
		return nres

	# ======================================================================================

	def replace_tab_by_test(self, query):
		"""
		      Relace all ``tab`` + doctype to ``test`` + doctype
		"""
		if self.is_testing:
			tl = self.get_testing_tables()
			for t in tl:
				query = query.replace(t, 'test' + t[3:])
		return query
		
	def get_testing_tables(self):
		"""
		      Get list of all tables for which `tab` is to be replaced by `test` before a query is executed
		"""
		if not self.testing_tables:
			testing_tables = ['tab'+r[0] for r in self.sql('SELECT name from tabDocType where docstatus<2 and (issingle=0 or issingle is null)', allow_testing = 0)]
			testing_tables+=['tabSeries','tabSingles'] # tabSessions is not included here
		return self.testing_tables

	# ======================================================================================
	# get a single value from a record

	def get_value(self, doctype, docname, fieldname):
		"""
		      Get a single / multiple value from a record.

		      For Single DocType, let docname be = None
		"""
			
		fl = fieldname
		if docname and (docname!=doctype or docname=='DocType'):
			if type(fieldname) in (list, tuple):
				fl = '`, `'.join(fieldname)

			r = self.sql("select `%s` from `tab%s` where name='%s'" % (fl, doctype, docname))
			return r and (len(r[0]) > 1 and r[0] or r[0][0]) or None
		else:
			if type(fieldname) in (list, tuple):
				fl = "', '".join(fieldname)

			r = self.sql("select value from tabSingles where field in ('%s') and doctype='%s'" % (fieldname, doctype))
			return r and (len(r) > 1 and (i[0] for i in r) or r[0][0]) or None

	def set_value(self, dt, dn, field, val):
		from webnotes.utils import now
		if dn and dt!=dn:
			self.sql("update `tab"+dt+"` set `"+field+"`=%s, modified=%s where name=%s", (val, now(), dn))
		else:
			if self.sql("select value from tabSingles where field=%s and doctype=%s", (field, dt)):
				self.sql("update tabSingles set value=%s where field=%s and doctype=%s", (val, field, dt))
			else:
				self.sql("insert into tabSingles(doctype, field, value) values (%s, %s, %s)", (dt, field, val))
				
	def set(self, doc, field, val):
		self.set_value(doc.doctype, doc.name, field, val)
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

	def exists(self, dt, dn):
		"""
		      Returns true if the record exists
		"""	
		try:
			return self.sql('select name from `tab%s` where name=%s' % (dt, '%s'), dn)
		except:
			return None

	# ======================================================================================
	def close(self):
		"""
		      Close my connection
		"""
		if self._conn:
			self._conn.close()
