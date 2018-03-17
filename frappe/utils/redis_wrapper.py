# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import redis, frappe, re
from six.moves import cPickle as pickle
import dill
from frappe.utils import cstr
from six import iteritems

class RedisWrapper(redis.Redis):
	"""Redis client that will automatically prefix conf.db_name"""
	def make_key(self, key, user=None, shared=False):
		if shared:
			return key
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

		def _set_value(instance, key, value, expires = 0, pickler = pickle):
			try:
				if expires:
					instance.setex(key, pickler.dumps(value), expires)
				else:
					instance.set(key, pickler.dumps(value))
			except redis.exceptions.ConnectionError:
				return None

		try:
			_set_value(key, val, expires = expires_in_sec, pickler = pickle)
		except TypeError:
			_set_value(key, val, expires = expires_in_sec, pickler = dill)

	def get_value(self, key, generator=None, user=None, expires=False):
		"""Returns cache value. If not found and generator function is
			given, it will call the generator.

		:param key: Cache key.
		:param generator: Function to be called to generate a value if `None` is returned.
		:param expires: If the key is supposed to be with an expiry, don't store it in frappe.local
		"""
		def _get_value(instance, key, generator=None, user=None, expires=False, pickler = pickle):
			original_key = key
			key = instance.make_key(key, user)

			if key in frappe.local.cache:
				val = frappe.local.cache[key]

			else:
				val = None
				try:
					val = instance.get(key)
				except redis.exceptions.ConnectionError:
					pass

				if val is not None:
					val = pickler.loads(val)

				if not expires:
					if val is None and generator:
						val = generator()
						instance.set_value(original_key, val, user=user)

					else:
						frappe.local.cache[key] = val

			return val

		try:
			return _get_value(self, key, generator, user, expires, pickler = pickle)
		except TypeError:
			return _get_value(self, key, generator, user, expires, pickler = dill)

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
			return [k for k in frappe.local.cache.keys() if regex.match(k.decode())]

	def delete_keys(self, key):
		"""Delete keys with wildcard `*`."""
		try:
			self.delete_value(self.get_keys(key), make_keys=False)
		except redis.exceptions.ConnectionError:
			pass

	def delete_key(self, *args, **kwargs):
		self.delete_value(*args, **kwargs)

	def delete_value(self, keys, user=None, make_keys=True, shared=False):
		"""Delete value, list of values."""
		if not isinstance(keys, (list, tuple)):
			keys = (keys, )

		for key in keys:
			if make_keys:
				key = self.make_key(key, shared=shared)

			if key in frappe.local.cache:
				del frappe.local.cache[key]

			try:
				self.delete(key)
			except redis.exceptions.ConnectionError:
				pass

	def lpush(self, key, value):
		super(redis.Redis, self).lpush(self.make_key(key), value)

	def rpush(self, key, value):
		super(redis.Redis, self).rpush(self.make_key(key), value)

	def lpop(self, key):
		return super(redis.Redis, self).lpop(self.make_key(key))

	def llen(self, key):
		return super(redis.Redis, self).llen(self.make_key(key))

	def hset(self, name, key, value, shared=False):
		_name = self.make_key(name, shared=shared)

		# set in local
		if not _name in frappe.local.cache:
			frappe.local.cache[_name] = {}
		frappe.local.cache[_name][key] = value

		# set in redis
		def _hset_value(instance, name, key, value, pickler = pickle):
			try:
				super(redis.Redis, instance).hset(name, key, pickler.dumps(value))
			except redis.exceptions.ConnectionError:
				pass

		# I'm not sure why we expect to pickle lambda objects.
		# But unfortunately, you cannot afford to, which silently fails.
		# dill although impressively slower should be used in case of such failures
		# both do serialize and deserialize.
		# One way was to try catch a lambda, but that is expected for each function call.
		# This also means there's a cost associated to a pickle failure (it then occurs twice).

		# if you think of a better solution, feel free to change RedisWrapper.

		try:
			_hset_value(self, _name, key, value, pickler = pickle)
		except TypeError:
			_hset_value(self, _name, key, value, pickler = dill)

	def hgetall(self, name):
		def _hgetall(instance, name, pickler = pickle):
			return {key: pickler.loads(value) for key, value in
				iteritems(super(redis.Redis, instance).hgetall(instance.make_key(name)))}
				
		try:
			return _hgetall(self, name, pickler = pickle)
		except TypeError:
			return _hgetall(self, name, pickler = dill)

	def hget(self, name, key, generator=None, shared=False):
		def _hget(instance, name, key, generator=None, shared=False, pickler = pickle):
			_name = instance.make_key(name, shared=shared)
			if not _name in frappe.local.cache:
				frappe.local.cache[_name] = {}

			if key in frappe.local.cache[_name]:
				return frappe.local.cache[_name][key]

			value = None
			try:
				value = super(redis.Redis, instance).hget(_name, key)
			except redis.exceptions.ConnectionError:
				pass

			if value:
				value = pickler.loads(value)
				frappe.local.cache[_name][key] = value
			elif generator:
				value = generator()
				try:
					instance.hset(name, key, value)
				except redis.exceptions.ConnectionError:
					pass
			return value

		try:
			return _hget(self, name, key, generator, shared, pickler = pickle)
		except ValueError:
			return _hget(self, name, key, generator, shared, pickler = dill)

	def hdel(self, name, key, shared=False):
		_name = self.make_key(name, shared=shared)

		if _name in frappe.local.cache:
			if key in frappe.local.cache[_name]:
				del frappe.local.cache[_name][key]
		try:
			super(redis.Redis, self).hdel(_name, key)
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


