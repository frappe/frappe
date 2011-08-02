"""
	Database Module
"""

import webnotes

class DatabaseRow:
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
	
	def get_clean(self):
		"""
			Returns record dict with only validcolumns
		"""
		columns = [d[0] for d in webnotes.conn.get_table_metadata(self.table)]
		tmp = {}
		for c in columns:
			tmp[c] = self.record.get(c, None)
		return tmp

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
		
class SingleRecord:
	def __init__(self, doctype, record):
		self.doctype = doctype
		self.record = record
		
	def update(self):
		"""
			Insert / Update a single record
		"""