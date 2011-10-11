class BaseModel:
	"""
		New style models will be inherited from this base model class
		This will contain methods for save update
		
		Standard attributes:
			_type
			_id
			_created_by
			_created_on
			_modified_by
			_modified_on
	"""
	def __init__(self, model_type = None, model_id = None, attributes = {}):
		self._type = model_type
		self._id = model_id
		if attributes:
			self.__dict__.update(attributes)
			
	def __getattr__(self, name):
		"""
			Getter is overridden so that it does not throw an exception
		"""
		if name in self.__dict__:
			return self.__dict__[name]
		else:
			return None
	
	def _read(self):
		"""
			Read
		"""
		self.__dict__.update(webnotes.conn.sql("""
			select * from `%s` where _id=%s
		""", (self._type, self._id), as_dict=1)[0])
	
	def _create(self):
		"""
			Create
		"""
		pass
	
	def _update(self):
		"""
			Update
		"""
		pass
		
	def _delete(self):
		"""
			Delete
		"""
		pass