# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 
from __future__ import unicode_literals

import memcache
from webnotes import conf

class MClient(memcache.Client):
	"""memcache client that will automatically prefix conf.db_name"""
	def n(self, key):
		return (conf.db_name + ":" + key.replace(" ", "_")).encode('utf-8')
	
	def set_value(self, key, val):
		self.set(self.n(key), val)
		
	def get_value(self, key, builder=None):
		if builder and conf.get("auto_cache_clear") or False:
			return builder()
			
		val = self.get(self.n(key))
		if not val and builder:
			val = builder()
			self.set_value(key, val)
		return val
		
	def delete_value(self, key):
		self.delete(self.n(key))
