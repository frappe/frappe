import webnotes
reserved = ['fields']

class Model:
	"""
		New style models will be inherited from this base model class
		This will contain methods for save update
		
		Standard attributes:
			type
			name
			owner
			creation
			modified_by
			modified_on
			
		Model persistence will be in subclasses
	"""
	_def = None
	
	def __init__(self, ttype = None, name = None, attributes = {}):
		self.type = ttype
		self.name = name
		if attributes:
			self.__dict__.update(attributes)
		
		# for bc
		self.fields = self.__dict__
			
	def __getattr__(self, name):
		"""
			Getter is overridden so that it does not throw an exception
		"""
		return self.__dict__.get(name, None)
		
	def get(self, name):
		"""
			Getter
		"""
		return self.__dict__.get(name, None)
		
	def load_def(self):
		"""
			Load the model meta data from file
		"""
		if not self._def:
			from webnotes.model.model_def import ModelDef
			self._def = ModelDef(self.type)
	
	def get_properties(self, **args):
		"""
			return properties
		"""
		self.load_def()
		
		fl = filter(lambda x: x.type=='DocField', self._def.children)

		# filter additional keywords
		if args:
			for key in args:
				fl = filter(lambda x: x.__dict__[key]==args[key], fl)
		
		return fl
	
	def _validate_select(self, prop, value):
		"""
			Raise validation exception
		"""
		if prop.options.startswith('link:'):
			if not webnotes.conn.exists(prop.options[5:], value):
				raise webnotes.InvalidOptionError
			
		elif not value in prop.options.split('\n'):
			raise webnotes.InvalidOptionError
		

	def _validate(self):
		"""
			Check data integrity before saving
		"""
		for prop in self.get_properties():
			value = self.__dict__.get(prop.fieldname)
			
			# link - this must be raised by the d
			# if prop.fieldtype == 'Link' and prop.options and value:
			#	if not webnotes.conn.exists(prop.options, value):
			#		raise webnotes.InvalidLinkError
				
			# select	
			if prop.fieldtype == 'Select' and prop.options: 
				self._validate_select(prop, value)
	
	def get_values(self):
		"""
			Returns dict of attributes except: 
			* starting with underscore (_)
			* functions
			* attribute "type"
		"""
		tmp = {}
		for key in self.__dict__:
			if not key.startswith('_') \
				and type(self.__dict__[key]).__name__ != 'function' \
				and key not in reserved:
			
				tmp[key] = self.__dict__[key]
		del tmp['type']
		return tmp

	def save(self, new=0):
		if new or not self.name:
			self.insert()
		else:
			self.update()

class DatabaseModel(Model):
	"""
		Model that is saved in database
	"""
	def __init__(self, ttype = None, name = None, attributes = {}):
		Model.__init__(self, ttype, name, attributes)
		if ttype and name and not attributes:
			self.read()
		
	def read(self):
		"""
			Read
		"""
		from webnotes.db.row import DatabaseRow
		self.__dict__.update(DatabaseRow('tab' + self.type).read(name=self.name))
		
	def insert(self):
		"""
			Create
		"""
		from webnotes.db.row import DatabaseRow
		self._validate()
		DatabaseRow('tab' + self.type, self.get_values()).insert()
			
	def update(self):
		"""
			Update
		"""
		self._validate()
		if not self.name:
			raise webnotes.NoNameError
		from webnotes.db.row import DatabaseRow, Single
		DatabaseRow('tab' + self.type, self.get_values()).update()
				
	def delete(self):
		"""
			Delete
		"""
		self._has_live_links()
		self._db_delete()


class SingleModel(Model):
	"""
		Static / Singleton Model (always in databases)
	"""
	def __init__(self, ttype = None, name = None, attributes = {}):
		Model.__init__(self, ttype, name, attributes)
		if ttype and name and not attributes:
			self.read()
		
	def read(self):
		"""
			Read
		"""
		tmp = webnotes.conn.sql("select field, value from tabSingles where type=%s", self.type)
		for t in tmp:
			self.__dict__[t[0]] = t[1]
	
	def insert(self):
		"""
			Insert
		"""
		self._validate()
		from webnotes.db.row import Single		
		Single(self.type, self.get_values()).update()

	def update(self):
		"""
			Update
		"""
		self._validate()
		from webnotes.db.row import Single		
		Single(self.type, self.get_values()).update()

	def delete(self):
		"""
			Delete
		"""
		from webnotes.db.row import Single		
		Single(self.type, {}).clear()
		