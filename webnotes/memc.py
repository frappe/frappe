# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 
from __future__ import unicode_literals

import memcache, webnotes

class MClient(memcache.Client):
	"""memcache client that will automatically prefix conf.db_name"""
	def n(self, key):
		return (webnotes.conf.db_name + ":" + key.replace(" ", "_")).encode('utf-8')
	
	def set_value(self, key, val):
		self.set(self.n(key), val)
		
	def get_value(self, key, builder=None):
		val = self.get(self.n(key))
		if not val and builder:
			val = builder()
			self.set_value(key, val)
		return val

	def delete_value(self, keys):
		if not isinstance(keys, (list, tuple)):
			keys = (keys,)
		for key in keys:
			self.delete(self.n(key))
