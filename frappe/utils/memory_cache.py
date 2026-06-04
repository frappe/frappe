# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import random
import re
import threading
import time

import frappe


class MemoryPipeline:
	def __init__(self, cache):
		self.cache = cache
		self.commands = []

	def __getattr__(self, name):
		def _func(*args, **kwargs):
			self.commands.append((name, args, kwargs))
			return self

		return _func

	def execute(self):
		ret = []
		for method_name, args, kwargs in self.commands:
			method = getattr(self.cache, method_name, None)
			if method:
				ret.append(method(*args, **kwargs))
		return ret


class MemoryCacheWrapper:
	"""
	In-memory cache that mirrors the RedisWrapper API.

	Used automatically as a fallback when Redis is unavailable (e.g. during
	local development or contributor onboarding). All existing code that uses
	``frappe.cache`` works without modification — no configuration required.

	Not suitable for production: cache is not shared across processes and is
	lost on restart.
	"""

	def __init__(self):
		self.cache = {}
		self.expiries = {}
		self.lock = threading.RLock()

	def __call__(self):
		"""WARNING: Added for backward compatibility to support frappe.cache().method(...)"""
		return self

	def ping(self):
		"""Ping the cache to check if it's alive (always returns True for memory cache)"""
		return True

	def connected(self):
		"""Check if cache is connected (always returns True for memory cache)"""
		return True

	def make_key(self, key, user=None, shared=False):
		if shared:
			return key

		if user:
			if user is True:
				user = frappe.local.session.get("user")

			key = f"user:{user}:{key}"

		return f"{frappe.local.conf.get('db_name')}|{key}"

	def set_value(self, key, val, user=None, expires_in_sec=None, shared=False):
		key = self.make_key(key, user, shared)

		frappe.local.cache[key] = val
		with self.lock:
			self.cache[key] = val
			if expires_in_sec:
				self.expiries[key] = time.time() + expires_in_sec

	def get_value(self, key, generator=None, user=None, expires=False, shared=False, *, use_local_cache=True):
		original_key = key
		key = self.make_key(key, user, shared)

		if key in frappe.local.cache and use_local_cache:
			return frappe.local.cache[key]

		val = None
		with self.lock:
			if key in self.cache:
				if key in self.expiries and time.time() > self.expiries[key]:
					del self.cache[key]
					del self.expiries[key]
				else:
					val = self.cache[key]

		if not expires:
			if val is None and generator:
				val = generator()
				self.set_value(original_key, val, user=user, shared=shared)
			else:
				frappe.local.cache[key] = val

		return val

	def get_all(self, key):
		ret = {}
		for k in self.get_keys(key):
			ret[key] = self.get_value(k)

		return ret

	def get_keys(self, key, user=None, shared=False):
		key = self.make_key(key + "*", user=user, shared=shared)
		pattern = str(key).replace("|", r"\|").replace("*", ".*")
		return [k for k in self.cache.keys() if re.match(pattern, str(k))]

	def delete_keys(self, key, user=None, shared=False):
		self.delete_value(self.get_keys(key, user=user, shared=shared), make_keys=False)

	def delete_key(self, *args, **kwargs):
		self.delete_value(*args, **kwargs)

	def delete_value(self, keys, user=None, make_keys=True, shared=False):
		if not keys:
			return

		if not isinstance(keys, list | tuple):
			keys = (keys,)

		if make_keys:
			keys = [self.make_key(k, shared=shared, user=user) for k in keys]

		for key in keys:
			frappe.local.cache.pop(key, None)

		with self.lock:
			for key in keys:
				self.cache.pop(key, None)
				self.expiries.pop(key, None)

	def lpush(self, key, value, user=None, shared=False):
		key = self.make_key(key, user=user, shared=shared)
		self.cache.setdefault(key, []).insert(0, value)

	def rpush(self, key, value):
		key = self.make_key(key)
		self.cache.setdefault(key, []).append(value)

	def lpop(self, key, user=None, shared=False):
		key = self.make_key(key, user=user, shared=shared)
		lst = self.cache.get(key)
		if lst:
			return lst.pop(0)

	def blpop(self, key, timeout=0, user=None, shared=False):
		if value := self.lpop(key, user=user, shared=shared):
			return value

		if timeout:
			time.sleep(timeout)
			return self.lpop(key, user=user, shared=shared)

	def rpop(self, key):
		key = self.make_key(key)
		lst = self.cache.get(key)
		if lst:
			return lst.pop()

	def llen(self, key):
		key = self.make_key(key)
		lst = self.cache.get(key)
		return len(lst) if lst else 0

	def lrange(self, key, start, stop):
		key = self.make_key(key)
		lst = self.cache.get(key, [])
		if stop == -1:
			stop = None
		else:
			stop += 1
		return lst[start:stop]

	def ltrim(self, key, start, stop):
		key = self.make_key(key)
		lst = self.cache.get(key, [])
		if stop == -1:
			stop = None
		else:
			stop += 1
		self.cache[key] = lst[start:stop]

	def hset(self, name, key, value, shared=False, **kwargs):
		_name = self.make_key(name, shared=shared)
		frappe.local.cache.setdefault(_name, {})[key] = value
		with self.lock:
			if _name not in self.cache:
				self.cache[_name] = {}
			if not isinstance(self.cache[_name], dict):
				self.cache[_name] = {}
			self.cache[_name][key] = value

	def hget(self, name, key, generator=None, shared=False):
		_name = self.make_key(name, shared=shared)
		val = self.cache.get(_name, {}).get(key)
		if val is None and generator:
			val = generator()
			self.hset(name, key, val, shared=shared)
		return val

	def hgetall(self, name):
		_name = self.make_key(name)
		return {
			(key.encode() if isinstance(key, str) else key): value
			for key, value in self.cache.get(_name, {}).items()
		}

	def hkeys(self, name):
		_name = self.make_key(name)
		return [key.encode() if isinstance(key, str) else key for key in self.cache.get(_name, {}).keys()]

	def hdel(self, name, keys, shared=False, pipeline=None):
		_name = self.make_key(name, shared=shared)
		if not isinstance(keys, list | tuple):
			keys = (keys,)
		for key in keys:
			if _name in self.cache and key in self.cache[_name]:
				del self.cache[_name][key]

	def hdel_keys(self, name_starts_with, key):
		for name in self.get_keys(name_starts_with):
			name = name.split("|", 1)[1]
			self.hdel(name, key)

	def hdel_names(self, names, key):
		"""Delete hash field from multiple hash names"""
		with self.lock:
			for name in names:
				_name = self.make_key(name)
				if _name in self.cache and isinstance(self.cache[_name], dict):
					self.cache[_name].pop(key, None)
				if _name in frappe.local.cache:
					frappe.local.cache[_name].pop(key, None)

	def hexists(self, name, key, shared=False):
		"""Check if hash field exists"""
		if key is None:
			return False
		_name = self.make_key(name, shared=shared)
		with self.lock:
			return _name in self.cache and isinstance(self.cache[_name], dict) and key in self.cache[_name]

	def exists(self, *names, user=None, shared=None):
		"""Check if keys exist"""
		count = 0
		keys = [self.make_key(n, user=user, shared=shared) for n in names]
		with self.lock:
			for key in keys:
				if key in self.cache:
					count += 1
		return count

	def expire_key(self, key, time_secs, user=None, shared=False):
		"""Set expiry time for a key"""
		key = self.make_key(key, user, shared)
		with self.lock:
			self.expiries[key] = time.time() + time_secs
		return True

	def sadd(self, name, *values):
		key = self.make_key(name)
		with self.lock:
			self.cache.setdefault(key, set()).update(values)

	def srem(self, name, *values):
		key = self.make_key(name)
		with self.lock:
			if key in self.cache:
				for v in values:
					self.cache[key].discard(v)

	def sismember(self, name, value):
		key = self.make_key(name)
		with self.lock:
			return value in self.cache.get(key, set())

	def smembers(self, name):
		key = self.make_key(name)
		with self.lock:
			return self.cache.get(key, set()).copy()

	def spop(self, name):
		"""Remove and return a random member from the set"""
		key = self.make_key(name)
		with self.lock:
			if cached_set := self.cache.get(key):
				return cached_set.pop()
		return None

	def srandmember(self, name, count=None):
		"""Return a random member from the set"""
		key = self.make_key(name)
		with self.lock:
			members = self.cache.get(key, set())
			if not members:
				return None
			if count is None:
				return random.choice(list(members))
			return random.sample(list(members), min(count, len(members)))

	def pipeline(self):
		return MemoryPipeline(self)

	def incrby(self, key, amount=1):
		with self.lock:
			self.cache[key] = self.cache.get(key, 0) + amount
			return self.cache[key]

	def expire(self, key, time_secs):
		with self.lock:
			self.expiries[key] = time.time() + time_secs
		return True

	def client_id(self):
		return 1

	def execute_command(self, *args, **kwargs):
		"""Stub for Redis execute_command — returns empty dict for INFO commands."""
		return {}

	def pubsub(self):
		"""Mock pubsub for compatibility with ClientCache"""

		class MockPubSub:
			def subscribe(self, **kwargs):
				pass

			def run_in_thread(self, **kwargs):
				class MockThread:
					def is_alive(self):
						return True

				return MockThread()

		return MockPubSub()
