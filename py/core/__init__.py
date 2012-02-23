# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
# 

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