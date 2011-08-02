class Model:
	"""
		New style models will be inherited from this base model class
		This will contain methods for save update
		
		Standard attributes:
			doctype
			name
			owner
			creation
			modified_by
			modified_on
	"""
	_def = None
	
	def __init__(self, doctype = None, name = None, attributes = {}):
		self.doctype = doctype
		self.name = name
		if attributes:
			self.__dict__.update(attributes)
		if doctype and name:
			self.read()
			
	def __getattr__(self, name):
		"""
			Getter is overridden so that it does not throw an exception
		"""
		return self.__dict__.get(name, None)
	
	def _load_model_def(self):
		"""
			Load the model meta data from file
		"""
		from webnotes.model.model_def import ModelDef
		self._def = ModelDef(doctype)
	
	def get_properties(self):
		"""
			return properties
		"""
		if not self._def:
			self._load_model_def()
			
		return filter(lambda x: x.doctype=='DocField', self._def.children)
		
	def read(self):
		"""
			Read
		"""
		self.__dict__.update(webnotes.conn.sql("""
			select * from `%s` where _id=%s
		""", (self._type, self.name), as_dict=1)[0])
	
	def set_name(self):
		"""
			Set name (id) for this record
		"""
		from webnotes.model.naming import NamingControl
		NamingControl(self, self._meta)
	
	def insert(self):
		"""
			Create
		"""
		self._validate()
		if not self.name:
			self.set_name()

		DatabaseRow('tab' + self.doctype, self.get_values()).insert()
		
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
		self._load_model_metadata()

		for prop in self.get_properties:
			value = self.__dict__.get(prop.fieldname)
			
			# link
			if prop.fieldtype == 'Link' and prop.options:
				if not webnotes.conn.exists(prop.options, value):
					raise webnotes.InvalidLinkError
				
			# select	
			elif prop.fieldtype == 'Select' and prop.options: 
				self._validate_select(prop, value)
			
			# mandatory
			if prop.reqd:
				if value in (None, ''):
					raise webnotes.MandatoryAttributeError
	
	def get_values(self):
		"""
			Returns dict of attributes except: 
			* starting with underscore (_)
			* functions
			* attribute "doctype"
		"""
		tmp = {}
		for key in __dict__:
			if not key.startswith('_') and type(self.__dict__[key]).__name__ != 'function':
				tmp[key] = self.__dict__[key]
		del tmp['doctype']
		return tmp
	
	def update(self):
		"""
			Update
		"""
		self._validate()
		from webnotes.db.row import DatabaseRow, Single
		DatabaseRow('tab' + self.doctype, self.get_values()).update()
				
	def delete(self):
		"""
			Delete
		"""
		self._has_live_links()
		self._db_delete()
		
	def rename(self, new_name):
		"""
			Rename model
		"""
		pass




class SingleModel(Model):
	"""
		Static / Singleton Model
	"""
	def __init__(self, doctype = None, name = None, attributes = {}):
		Model.__init__(self, doctype, name, attributes)
		
	def read(self):
		"""
			Read
		"""
		tmp = webnotes.conn.sql("select field, value from tabSingles where doctype=%s", self.doctype)
		for t in tmp:
			self.__dict__[t[0]] = t[1]
	
	def insert(self):
		"""
			Insert
		"""
		self._validate()
		from webnotes.db.row import Single		
		Single(self.doctype, self.get_values()).update()

	def update(self):
		"""
			Update
		"""
		self._validate()
		from webnotes.db.row import Single		
		Single(self.doctype, self.get_values()).update()

	def delete(self):
		"""
			Delete
		"""
		from webnotes.db.row import Single		
		Single(self.doctype, {}).clear()
		