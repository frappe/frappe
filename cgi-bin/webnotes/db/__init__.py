import webnotes

# stanard error codes

NO_TABLE = 1146
NO_COLUMN = 1054

class Database:
	"""
	   Open a database connection with the given parmeters, if use_default is True, use the
	   login details from `defs.py`. This is called by the request handler and is accessible using
	   the `conn` global variable. the `sql` method is also global to run queries
	"""
	max_writes = 5000
	table_metadata = {}
	is_testing = 0
	in_transaction = 0
	transaction_writes = 0
	
	def __init__(self, host=None, user=None, password=None, ac_name=None, use_default = 0):
		"""
			Connect on creation
		"""
		from webnotes import defs
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
		
		# connect
		self.connect()
		if self.user != 'root':
			self.use(self.user)

		
	def get_db_login(self, ac_name):
		return getattr(defs,'db_name_map').get(ac_name, getattr(defs,'default_db_name'))

	def connect(self):
		"""
		      Connect to a database
		"""
		import MySQLdb
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
		"""
			Execute a query
		"""
		from webnotes.db.query import DatabaseQuery
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

	def get_table_metadata(self, table):
		"""
			returns table description
		"""
		if not table in self.table_metadata:
			self.table_metadata[table] = self.sql('desc `%s`' % table)
		
		return self.table_metadata[table]			

	def close(self):
		"""
		      Close my connection
		"""
		if self._conn:
			self._conn.close()