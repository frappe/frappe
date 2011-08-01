class Model:
	"""
		New style models will be inherited from this base model class
		This will contain methods for save update
		
		Standard attributes:
			_type
			name
			created_by
			created_on
			modified_by
			modified_on
	"""
	def __init__(self, doctype = None, name = None, attributes = {}):
		self.doctype = doctype
		self.name = name
		if attributes:
			self.__dict__.update(attributes)
		self._meta = Meta(doctype)
			
	def __getattr__(self, name):
		"""
			Getter is overridden so that it does not throw an exception
		"""
		if name in self.__dict__:
			return self.__dict__[name]
		else:
			return None
	
	def _load_model_metadata(self):
		"""
			Load the model meta data from file
		"""
		pass
	
	def _read(self):
		"""
			Read
		"""
		self.__dict__.update(webnotes.conn.sql("""
			select * from `%s` where _id=%s
		""", (self._type, self.name), as_dict=1)[0])
	
	def _set_name(self):
		"""
			Set name (id) for this record
		"""
		from webnotes.model.naming import NamingControl
		NamingControl(self, self._meta)
	
	def _insert(self):
		"""
			Create
		"""
		self._validate()
		if not self.name:
			self._set_name()
		self._db_insert()

	def _validate(self):
		"""
			Check data integrity before saving
		"""
		self._load_model_metadata()
		self._validate_links()
		self._validate_options()
		self._validate_mandatory()
		if hasattr(self, 'validate'):
			self.validate()
	
	def _update(self):
		"""
			Update
		"""
		self._validate()
		self._db_update()
		
	def _delete(self):
		"""
			Delete
		"""
		self._has_live_links()
		self._db_delete()
		
	def _rename(self, new_name):
		"""
			Rename model
		"""
		pass
	
