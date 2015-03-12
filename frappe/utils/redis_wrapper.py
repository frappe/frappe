# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import redis, frappe, pickle

class RedisWrapper(redis.Redis):
	"""Redis client that will automatically prefix conf.db_name"""
	def make_key(self, key, user=None):
		if user:
			if user == True:
				user = frappe.session.user

			key = "user:{0}:{1}".format(user, key)

		return (frappe.conf.db_name + "|" + key).encode('utf-8')

	def set_value(self, key, val, user=None):
		"""Sets cache value."""
		key = self.make_key(key, user)
		frappe.local.cache[key] = val
		if frappe.local.flags.in_install:
			return

		try:
			self.set(key, pickle.dumps(val))
		except redis.exceptions.ConnectionError:
			return None

	def get_value(self, key, generator=None, user=None):
		"""Returns cache value. If not found and generator function is
			given, it will call the generator.

		:param key: Cache key.
		:param generator: Function to be called to generate a value if `None` is returned."""
		original_key = key
		key = self.make_key(key, user)
		val = frappe.local.cache.get(key)

		if val is None:
			if not frappe.local.flags.in_install:
				try:
					val = self.get(key)
				except redis.exceptions.ConnectionError:
					pass
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
		try:
			return self.keys(self.make_key(key + "*"))
		except redis.exceptions.ConnectionError:
			return []

	def delete_keys(self, key):
		"""Delete keys with wildcard `*`."""
		try:
			self.delete_value(self.get_keys(key), make_keys=False)
		except redis.exceptions.ConnectionError:
			pass

	def delete_value(self, keys, user=None, make_keys=True):
		"""Delete value, list of values."""
		if not isinstance(keys, (list, tuple)):
			keys = (keys, )

		for key in keys:
			if make_keys:
				key = self.make_key(key)


			if not frappe.local.flags.in_install:
				try:
					self.delete(key)
				except redis.exceptions.ConnectionError:
					pass

			if key in frappe.local.cache:
				del frappe.local.cache[key]
