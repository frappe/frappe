# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
# MIT License. See license.txt 
from __future__ import unicode_literals

import memcache, conf

class MClient(memcache.Client):
	"""memcache client that will automatically prefix conf.db_name"""
	def n(self, key):
		return (conf.db_name + ":" + key.replace(" ", "_")).encode('utf-8')
	
	def set_value(self, key, val):
		self.set(self.n(key), val)
		
	def get_value(self, key):
		return self.get(self.n(key))
		
	def delete_value(self, key):
		self.delete(self.n(key))