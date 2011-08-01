"""
	Database Module
"""

import MySQLdb
from webnotes import defs
import webnotes

class Database:
	"""
	   Open a database connection with the given parmeters, if use_default is True, use the
	   login details from `defs.py`. This is called by the request handler and is accessible using
	   the `conn` global variable. the `sql` method is also global to run queries
	"""
	max_writes = 5000
	
	def __init__(self, host=None, user=None, password=None, ac_name=None, use_default = 0):
		self.host = host or 'localhost'
		self.user = user or getattr(defs, 'default_db_name', '')

		# password can be empty string
		self.password = password
		if password==None:
			self.password = getattr(defs, 'db_password', '')

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
		
	def sql(self, query, values=(), as_dict = 0, as_list = 0, formatted = 0, debug=0, ignore_ddl=0):
		query = DatabaseQuery(self, query)
		
		query.execute(values, debug, ignore_ddl)
		if as_dict:
			return query.fetch_as_dict(formatted)
		else:
			return query.fetch_as_list(formatted)

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
		"""
			Set value in a record
		"""
		from webnotes.utils import now
		if dn and dt!=dn:
			self.sql("update `tab"+dt+"` set `"+field+"`=%s, modified=%s where name=%s", (val, now(), dn))
		else:
			self.set_value_single(dt, field, val)
			
	def set_value_single(self, dt, field, val):
		"""
			Set value in a single record
		"""
		if self.sql("select value from tabSingles where field=%s and doctype=%s", (field, dt)):
			self.sql("update tabSingles set value=%s where field=%s and doctype=%s", (val, field, dt))
		else:
			self.sql("insert into tabSingles(doctype, field, value) values (%s, %s, %s)", (dt, field, val))
				
	def set(self, doc, field, val):
		"""
			Set a value in a model locally and update it
		"""
		self.set_value(doc.doctype, doc.name, field, val)
		doc.fields[field] = val

	def set_global(self, key, val, user='__global'):
		"""
			set a global value
		"""
		res = self.sql('select defkey from `tabDefaultValue` where defkey=%s and parent=%s', (key, user))
		if res:
			self.sql('update `tabDefaultValue` set defvalue=%s where parent=%s and defkey=%s', (str(val), user, key))
		else:
			self.sql('insert into `tabDefaultValue` (name, defkey, defvalue, parent) values (%s,%s,%s,%s)', (user+'_'+key, key, str(val), user))

	def get_global(self, key, user='__global'):
		"""
			get global value
		"""
		g = self.sql("select defvalue from tabDefaultValue where defkey=%s and parent=%s", (key, user))
		return g and g[0][0] or None

	def begin(self):
		"""
			START TRANSACTION
		"""
		if not self.in_transaction:
			self.sql("start transaction")
	
	def commit(self):
		"""
			COMMIT
		"""
		self.sql("commit")

	def rollback(self):
		"""
			ROLLBACK
		"""
		self.sql("ROLLBACK")


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

	def close(self):
		"""
		      Close my connection
		"""
		if self._conn:
			self._conn.close()
			
class DatabaseQuery:
	"""
		Wrapper Around db query
	"""
	def __init__(self, db, query):
		self.query = query
		self.db = db

	def is_write(self):
		"""
			Returns true if query is insert or update
		"""
		if self.command() in ['update', 'insert']:
			return True
			
	def command(self):
		"""
			Returns sql command
		"""
		if self.query:
			return self.query.strip().split()[0].lower()

	def check_transaction_status(self):
		"""
		      Update *in_transaction* and check if "START TRANSACTION" is not called twice
		"""
		query = self.query
		
		if self.db.in_transaction and self.command() in ['start', 'alter', 'drop', 'create']:
			raise Exception, 'This statement can cause implicit commit'

		if query and query.strip().lower()=='start transaction':
			self.db.in_transaction = 1
			self.db.transaction_writes = 0
			
		if query and self.command() in ['commit', 'rollback']:
			self.db.in_transaction = 0

	def check_too_many_writes(self):
		"""
			Test if there are too many writes (more than max_writes)
		"""
		query = self.query
		if self.db.in_transaction and self.is_write():
			self.db.transaction_writes += 1
			if self.db.transaction_writes > self.db.max_writes:
				webnotes.msgprint('A very long query was encountered. If you are trying to import data, please do so using smaller files')
				raise Exception, 'Bad Query!!! Too many writes'
	
	def fetch_as_dict(self, formatted=0):
		"""
		      Internal - get results as dictionary
		"""
		result = self.db._cursor.fetchall()
		desc = self.db._cursor.description
		
		ret = []
		for r in result:
			tmp = {}
			for i in range(len(r)):
				tmp[desc[i][0]] = self.convert_to_simple_type(r[i], formatted)
			ret.append(tmp)
		return ret
	
	def validate_query(self, q):
		"""
			Validate that ddl are executed by Administrator only
		"""
		if self.command() in ['alter', 'drop', 'truncate'] and webnotes.user.name != 'Administrator':
			webnotes.msgprint('Not allowed to execute query')
			raise Execption
	
	def execute(self, values=(), debug=0, ignore_ddl=0):
		"""
		      * Execute a `query`, with given `values`
		      * returns as a dictionary if as_dict = 1
		      * returns as a list of lists (with cleaned up dates and decimals) if as_list = 1
		"""			
		# in transaction validations
		self.check_transaction_status()
		self.check_too_many_writes()
			
			
		cursor = self.db._cursor
		# execute
		try:
			if values!=():
				cursor.execute(self.query, values)
				if debug: webnotes.msgprint(self.query % values)
				
			else:
				cursor.execute(self.query)	
				if debug: webnotes.msgprint(self.query)

		except Exception, e:
			# ignore data definition errors
			if ignore_ddl and e.args[0] in (1146,1054,1091):
				pass
			else:
				raise e

	def fetch_as_list(self, formatted=0):
		"""
		      Convert the given result set to a list of lists (with cleaned up dates and decimals)
		"""
		res = self.db._cursor.fetchall()
		return [[self.convert_to_simple_type(c, formatted) for c in row] for row in res]

	def get_description(self):
		"""
		      Get metadata of the last query
		"""
		return self.db._cursor.description

	def convert_to_simple_type(self, v, formatted=0):
		"""
			Convert data to simple types
			(Use JSON instead)
		"""
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

class DatabaseRecord:
	"""
		Represents a database record
	"""
	def __init__(self, table, record):
		self.record = record
		self.table = table
	
	def prepare_insert(self):
		"""
			Prepare for insert
		"""
		from webnotes.utils import now
		n = now()
		self.record.update({
			'owner': webnotes.session['user'],
			'modified_by': webnotes.session['user'],
			'creation': n,
			'modified_on': n
		})
			
	def insert(self):
		"""
			Build an insert query and execute it
		"""
		self.prepare()
		query = "insert into `%s` (%s) values (%s)"

	def update(self):
		"""
			Build an update query and execute it
		"""

	def delete(self):
		"""
			Delete by name
		"""
		
class SingleRecord:
	def __init__(self, doctype, record):
		self.doctype = doctype
		self.record = record
		