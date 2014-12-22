# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import redis, frappe, cPickle as pickle

class RedisWrapper(redis.Redis):
	"""Redis client that will automatically prefix conf.db_name"""
	def make_key(self, key, user=None):
		if user:
			print user
			if user == True:
				user = frappe.session.user

			key = "user:{0}:{1}".format(user, key)

		return (frappe.conf.db_name + "|" + key).encode('utf-8')

	def set_value(self, key, val, user=None):
		"""Sets cache value."""
		key = self.make_key(key, user)
		frappe.local.cache[key] = val
		self.set(key, pickle.dumps(val))

	def get_value(self, key, generator=None, user=None):
		"""Returns cache value. If not found and generator function is
			given, it will call the generator.

		:param key: Cache key.
		:param generator: Function to be called to generate a value if `None` is returned."""
		original_key = key
		key = self.make_key(key, user)
		val = frappe.local.cache.get(key)
		if val is None:
			val = self.get(key)
			if val is not None:
				val = pickle.loads(val)
			if val is None and generator:
				val = generator()
				self.set_value(original_key, val, user=user)
			else:
				frappe.local.cache[key] = val
		return val

	def get_all(self, key):
		ret = {}
		for k in self.get_keys(key):
			ret[key] = self.get_value(k)

		return ret

	def get_keys(self, key):
		"""Return keys with wildcard `*`."""
		return self.keys(self.make_key(key + "*"))

	def delete_keys(self, key):
		"""Delete keys with wildcard `*`."""
		self.delete_value(self.get_keys(key))

	def delete_value(self, keys, user=None):
		"""Delete value, list of values."""
		if not isinstance(keys, (list, tuple)):
			keys = (keys,)
		for key in keys:
			key = self.make_key(key, user=user)
			self.delete(key)
			if key in frappe.local.cache:
				del frappe.local.cache[key]
