# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt 
from __future__ import unicode_literals

import memcache, frappe

class MClient(memcache.Client):
	"""memcache client that will automatically prefix conf.db_name"""
	def n(self, key):
		return (frappe.conf.db_name + ":" + key.replace(" ", "_")).encode('utf-8')
	
	def set_value(self, key, val):
		frappe.local.cache[key] = val
		self.set(self.n(key), val)
		
	def get_value(self, key, builder=None):
		val = frappe.local.cache.get(key)
		if val is None:
			val = self.get(self.n(key))
			if val is None and builder:
				val = builder()
				self.set_value(key, val)
			else:
				frappe.local.cache[key] = val
		return val

	def delete_value(self, keys):
		if not isinstance(keys, (list, tuple)):
			keys = (keys,)
		for key in keys:
			self.delete(self.n(key))
			if key in frappe.local.cache:
				del frappe.local.cache[key]
