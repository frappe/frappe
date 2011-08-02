import webnotes


type_map = {
	'currency':		('decimal', '14,2')
	,'int':			('int', '11')
	,'float':		('decimal', '14,6')
	,'check':		('int', '1')
	,'small text':	('text', '')
	,'long text':	('text', '')
	,'code':		('text', '')
	,'text editor':	('text', '')
	,'date':		('date', '')
	,'time':		('time', '')
	,'text':		('text', '')
	,'data':		('varchar', '180')
	,'link':		('varchar', '180')
	,'password':	('varchar', '180')
	,'select':		('varchar', '180')
	,'read only':	('varchar', '180')
	,'blob':		('longblob', '')
}

default_shortcuts = ['_Login', '__user', '_Full Name', 'Today', '__today']

class DatabaseColumn:
	"""
		Class for Database Column
	"""
	def __init__(self, table, fieldname, fieldtype, length, default, set_index, options):
		self.table = table
		self.fieldname = fieldname
		self.fieldtype = fieldtype
		self.length = length
		self.set_index = set_index
		self.default = default
		self.options = options

	def get_definition(self, with_default=1):
		d = type_map.get(self.fieldtype.lower())

		if not d:
			return
			
		ret = d[0]
		if d[1]:
			ret += '(' + d[1] + ')'
		if with_default and self.default and (self.default not in default_shortcuts):
			ret += ' default "' + self.default.replace('"', '\"') + '"'
		return ret
	
	def has_index(self):
		"""
			Returns true if table has index
		"""
		if self.set_index and type_map.get(self.fieldtype) and \
			type_map.get(self.fieldtype.lower())[0] not in ('text', 'blob'):
			return True
	
	def get_index_def(self):
		"""
			Get index definition
		"""
		return 'index `' + self.fieldname + '`(`' + self.fieldname + '`)'
		
	def check(self, current_def):
		"""
			Updates table if there is any difference between current and main
		"""
		column_def = self.get_definition(0)

		# no columns
		if not column_def:
			return
		
		# to add?
		if not current_def:
			self.fieldname = self.validate_column_name()
			self.table.add_column.append(self)
			return

		# type
		if current_def['type'] != column_def:
			self.table.change_type.append(self)
		
		# index
		else:
			if (current_def['index'] and not self.set_index):
				self.table.drop_index.append(self)
			
			if (not current_def['index'] and self.set_index and not (column_def in ['text','blob'])):
				self.table.add_index.append(self)
		
		# default
		if (self.default and (current_def['default'] != self.default) and (self.default not in default_shortcuts) and not (column_def in ['text','blob'])):
			self.table.set_default.append(self)

	def validate_column_name(self):
		"""
			Raises exception for invalid column name
		"""
		n = self.fieldname
		n = n.replace(' ','_').strip().lower()
		import re
		if not re.match("[a-zA-Z_][a-zA-Z0-9_]*$", n):
			webnotes.msgprint('err:%s is not a valid fieldname.<br>A valid name must contain letters / numbers / spaces.<br><b>Tip: </b>You can change the Label after the fieldname has been set' % n)
			raise Exception
		return n