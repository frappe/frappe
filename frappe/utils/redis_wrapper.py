# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import redis, frappe, re
import cPickle as pickle
from frappe.utils import cstr

class RedisWrapper(redis.Redis):
	"""Redis client that will automatically prefix conf.db_name"""
	def make_key(self, key, user=None):
		if user:
			if user == True:
				user = frappe.session.user

			key = "user:{0}:{1}".format(user, key)

		return "{0}|{1}".format(frappe.conf.db_name, key).encode('utf-8')

	def set_value(self, key, val, user=None, expires_in_sec=None):
		"""Sets cache value.

		:param key: Cache key
		:param val: Value to be cached
		:param user: Prepends key with User
		:param expires_in_sec: Expire value of this key in X seconds
		"""
		key = self.make_key(key, user)

		if not expires_in_sec:
			frappe.local.cache[key] = val

		try:
			if expires_in_sec:
				self.setex(key, pickle.dumps(val), expires_in_sec)
			else:
				self.set(key, pickle.dumps(val))

		except redis.exceptions.ConnectionError:
			return None

	def get_value(self, key, generator=None, user=None, expires=False):
		"""Returns cache value. If not found and generator function is
			given, it will call the generator.

		:param key: Cache key.
		:param generator: Function to be called to generate a value if `None` is returned.
		:param expires: If the key is supposed to be with an expiry, don't store it in frappe.local
		"""
		original_key = key
		key = self.make_key(key, user)

		if key in frappe.local.cache:
			val = frappe.local.cache[key]

		else:
			val = None
			try:
				val = self.get(key)
			except redis.exceptions.ConnectionError:
				pass

			if val is not None:
				val = pickle.loads(val)

			if not expires:
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
		"""Return keys starting with `key`."""
		try:
			key = self.make_key(key + "*")
			return self.keys(key)

		except redis.exceptions.ConnectionError:
			regex = re.compile(cstr(key).replace("|", "\|").replace("*", "[\w]*"))
			return [k for k in frappe.local.cache.keys() if regex.match(k)]

	def delete_keys(self, key):
		"""Delete keys with wildcard `*`."""
		try:
			self.delete_value(self.get_keys(key), make_keys=False)
		except redis.exceptions.ConnectionError:
			pass

	def delete_key(self, *args, **kwargs):
		self.delete_value(*args, **kwargs)

	def delete_value(self, keys, user=None, make_keys=True):
		"""Delete value, list of values."""
		if not isinstance(keys, (list, tuple)):
			keys = (keys, )

		for key in keys:
			if make_keys:
				key = self.make_key(key)

			try:
				self.delete(key)
			except redis.exceptions.ConnectionError:
				pass

			if key in frappe.local.cache:
				del frappe.local.cache[key]

	def lpush(self, key, value):
		super(redis.Redis, self).lpush(self.make_key(key), value)

	def rpush(self, key, value):
		super(redis.Redis, self).rpush(self.make_key(key), value)

	def lpop(self, key):
		return super(redis.Redis, self).lpop(self.make_key(key))

	def llen(self, key):
		return super(redis.Redis, self).llen(self.make_key(key))

	def hset(self, name, key, value):
		if not name in frappe.local.cache:
			frappe.local.cache[name] = {}
		frappe.local.cache[name][key] = value
		try:
			super(redis.Redis, self).hset(self.make_key(name), key, pickle.dumps(value))
		except redis.exceptions.ConnectionError:
			pass

	def hgetall(self, name):
		return {key: pickle.loads(value) for key, value in
			super(redis.Redis, self).hgetall(self.make_key(name)).iteritems()}

	def hget(self, name, key, generator=None):
		if not name in frappe.local.cache:
			frappe.local.cache[name] = {}
		if key in frappe.local.cache[name]:
			return frappe.local.cache[name][key]

		value = None
		try:
			value = super(redis.Redis, self).hget(self.make_key(name), key)
		except redis.exceptions.ConnectionError:
			pass

		if value:
			value = pickle.loads(value)
			frappe.local.cache[name][key] = value
		elif generator:
			value = generator()
			try:
				self.hset(name, key, value)
			except redis.exceptions.ConnectionError:
				pass
		return value

	def hdel(self, name, key):
		if name in frappe.local.cache:
			if key in frappe.local.cache[name]:
				del frappe.local.cache[name][key]
		try:
			super(redis.Redis, self).hdel(self.make_key(name), key)
		except redis.exceptions.ConnectionError:
			pass

	def hdel_keys(self, name_starts_with, key):
		"""Delete hash names with wildcard `*` and key"""
		for name in frappe.cache().get_keys(name_starts_with):
			name = name.split("|", 1)[1]
			self.hdel(name, key)

	def hkeys(self, name):
		try:
			return super(redis.Redis, self).hkeys(self.make_key(name))
		except redis.exceptions.ConnectionError:
			return []


