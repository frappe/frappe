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
	def __init__(self, doctype = None, name = None, attributes = {}):
		self.doctype = doctype
		self.name = name
		if attributes:
			self.__dict__.update(attributes)
		if doctype and name:
			self._read()
			
	def __getattr__(self, name):
		"""
			Getter is overridden so that it does not throw an exception
		"""
		return self.__dict__.get(name, None)
	
	def _load_model_metadata(self):
		"""
			Load the model meta data from file
		"""
		from webnotes.model.meta import Meta
		self._meta = Meta(doctype)
	
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

		DatabaseRow('tab' + self.doctype, self._get_values()).insert()

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
	
	def _get_values(self):
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
	
	def _update(self):
		"""
			Update
		"""
		self._validate()
		from webnotes.db.row import DatabaseRow, Single
		DatabaseRow('tab' + self.doctype, self._get_values()).update()
				
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
	
class SingleModel(Model):
	"""
		Static / Singleton Model
	"""
	def __init__(self, doctype = None, name = None, attributes = {}):
		Model.__init__(self, doctype, name, attributes)
		
	def _read(self):
		"""
			Read
		"""
		tmp = webnotes.conn.sql("select field, value from tabSingles where doctype=%s", self.doctype)
		for t in tmp:
			self.__dict__[t[0]] = t[1]
	
	def _insert(self):
		"""
			Insert
		"""
		self._validate()
		from webnotes.db.row import Single		
		Single(self.doctype, self._get_values()).update()

	def _update(self):
		"""
			Update
		"""
		self._validate()
		from webnotes.db.row import Single		
		Single(self.doctype, self._get_values()).update()
