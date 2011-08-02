			
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
