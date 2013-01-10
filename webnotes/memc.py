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
from __future__ import unicode_literals

import memcache, conf

class MClient(memcache.Client):
	"""memcache client that will automatically prefix conf.db_name
	and maintain a key list"""
	def n(self, key):
		return (conf.db_name + ":" + key.replace(" ", "_")).encode('utf-8')
	
	def set_value(self, key, val):
		self.set(self.n(key), val)
		self.add_to_key_list(key)
		
	def get_value(self, key):
		return self.get(self.n(key))
		
	def delete_value(self, key):
		self.delete(self.n(key))
		
	def add_to_key_list(self, key):
		key_list = self.get_value('key_list') or []
		if key not in key_list:
			key_list.append(key)
		self.set(self.n("key_list"), key_list)
		
	def delete_keys(self, startswith=None):
		"""flush keys from known key_list"""
		if not startswith:
			for key in self.get_value('key_list'):
				self.delete_value(key)

			self.delete_value('key_list')
		else:
			deleted = []
			keys = self.get_value('key_list') or []
			for key in keys:
				if key.startswith(startswith):
					self.delete(self.n(key))
					deleted.append(key)
					
			for d in deleted:
				keys.remove(d)
			
			self.set_value("key_list", keys)
			# in any case, delete it explicitly
			self.delete(self.n(startswith))
