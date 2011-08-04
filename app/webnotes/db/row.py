"""
	Database Module
"""

import webnotes

class DatabaseRow:
	"""
		Represents a database record
	"""
	def __init__(self, table, record=None):
		self.record = record
		self.table = table

	def get_conditions(self, columns):
		"""
			Converts arguments to db conditions
		"""
		return ' AND '.join(['`%s`=%s' % (c, '%s') for c in columns])

	def read(self, **args):
		"""
			Read the record based on arguments
		"""
		self.record = webnotes.conn.sql("select * from `%s` where %s" % \
			(self.table, self.get_conditions(args.keys())), args.values(), as_dict=1)[0]
		return self.record

	def get_clean(self):
		"""
			Returns record dict with only validcolumns
		"""
		columns = [d[0] for d in webnotes.conn.get_table_metadata(self.table)]
		tmp = {}
		for c in columns:
			tmp[c] = self.record.get(c, None)
		return tmp
	
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
		self.prepare_insert()
		tmp = self.get_clean()
		keys = ['`' + k + '`' for k in tmp.keys()]
		
		query = "insert into `%s` (%s) values (%s)" % \
			(self.table, ', '.join(keys), ', '.join(['%s']*len(keys)))
		
		webnotes.conn.sql(query, tmp.values())

	def prepare_update(self):
		"""
			Prepare for update
		"""
		from webnotes.utils import now
		n = now()
		self.record.update({
			'modified_by': webnotes.session['user'],
			'modified_on': n
		})
		
	def update(self):
		"""
			Build an update query and execute it
		"""
		if not self.record.get('name'):
			raise Exception, "No primary key for update"
			
		self.prepare_insert()
		tmp = self.get_clean()
		keys = ['`' + k + '`=%s' for k in tmp.keys()]
		values = tmp.values() + [tmp['name']]

		query = "update `%s` set %s where name=%s" % \
			(self.table, ', '.join(keys), '%s')
		webnotes.conn.sql(query, values)

	def delete(self):
		"""
			Delete by name
		"""
		pass
		
class Single:
	def __init__(self, doctype, record):
		self.doctype = doctype
		self.record = record

	def clear(self):
		"""
			Clear single
		"""
		# clear
		webnotes.conn.sql("delete from tabSingles where doctype='%s'" % self.doctype)

	def update(self):
		"""
			Insert / Update a single record
		"""
		self.clear()
		values = []
		
		# build list of values
		for key in self.record:
			values += [self.doctype, key, self.record[key]]
		
		# build the query
		query = 'insert into tabSingles(doctype, field, value) values %s' %\
		 	(', '.join(['(%s, %s, %s)'] * len(self.record.keys())))
		
		# insert
		webnotes.conn.sql(query, values)