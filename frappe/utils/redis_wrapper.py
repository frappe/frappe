# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json
import pickle
import re
import threading
import time
import typing
from collections import namedtuple
from contextlib import suppress

import redis
from redis.commands.search import Search
from redis.exceptions import ResponseError

import frappe
from frappe.utils import cstr

# 5 is faster than default which is 4.
# Python uses old protocol for backward compatibility, we don't support anything <3.10.
DEFAULT_PICKLE_PROTOCOL = 5


class RedisearchWrapper(Search):
	def sugadd(self, key, *suggestions, **kwargs):
		return super().sugadd(self.client.make_key(key), *suggestions, **kwargs)

	def suglen(self, key):
		return super().suglen(self.client.make_key(key))

	def sugdel(self, key, string):
		return super().sugdel(self.client.make_key(key), string)

	def sugget(self, key, *args, **kwargs):
		return super().sugget(self.client.make_key(key), *args, **kwargs)


class RedisWrapper(redis.Redis):
	"""Redis client that will automatically prefix conf.db_name"""

	def connected(self):
		try:
			self.ping()
			return True
		except redis.exceptions.ConnectionError:
			return False

	def __call__(self):
		"""WARNING: Added for backward compatibility to support frappe.cache().method(...)"""
		return self

	def make_key(self, key, user=None, shared=False):
		if shared:
			return key

		if user:
			if user is True:
				user = frappe.local.session.get("user")

			key = f"user:{user}:{key}"

		return f"{frappe.local.conf.get('db_name')}|{key}".encode()

	def set_value(self, key, val, user=None, expires_in_sec=None, shared=False):
		"""Sets cache value.

		:param key: Cache key
		:param val: Value to be cached
		:param user: Prepends key with User
		:param expires_in_sec: Expire value of this key in X seconds
		"""
		key = self.make_key(key, user, shared)

		frappe.local.cache[key] = val

		with suppress(redis.exceptions.ConnectionError):
			self.set(name=key, value=pickle.dumps(val, protocol=DEFAULT_PICKLE_PROTOCOL), ex=expires_in_sec)

	def get_value(self, key, generator=None, user=None, expires=False, shared=False, *, use_local_cache=True):
		"""Return cache value. If not found and generator function is
		        given, call the generator.

		:param key: Cache key.
		:param generator: Function to be called to generate a value if `None` is returned.
		:param expires: If the key is supposed to be with an expiry, don't store it in frappe.local
		"""
		original_key = key
		key = self.make_key(key, user, shared)

		local_cache = frappe.local.cache
		if key in local_cache and use_local_cache:
			val = local_cache[key]

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
					self.set_value(original_key, val, user=user, shared=shared)

				else:
					local_cache[key] = val

		return val

	def expire_key(self, key, time, *, user=None, shared=False):
		key = self.make_key(key, user, shared)
		try:
			return self.expire(key, time)
		except redis.exceptions.ConnectionError:
			pass

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
			regex = re.compile(cstr(key).replace("|", r"\|").replace("*", r"[\w]*"))
			return [k for k in list(frappe.local.cache) if regex.match(cstr(k))]

	def delete_keys(self, key):
		"""Delete keys with wildcard `*`."""
		self.delete_value(self.get_keys(key), make_keys=False)

	def delete_key(self, *args, **kwargs):
		self.delete_value(*args, **kwargs)

	def delete_value(self, keys, user=None, make_keys=True, shared=False):
		"""Delete value, list of values."""
		if not keys:
			return

		if not isinstance(keys, list | tuple):
			keys = (keys,)

		if make_keys:
			keys = [self.make_key(k, shared=shared, user=user) for k in keys]

		local_cache = frappe.local.cache
		for key in keys:
			local_cache.pop(key, None)

		try:
			self.unlink(*keys)
		except redis.exceptions.ConnectionError:
			pass

	def lpush(self, key, value):
		return super().lpush(self.make_key(key), value)

	def rpush(self, key, value):
		return super().rpush(self.make_key(key), value)

	def lpop(self, key):
		return super().lpop(self.make_key(key))

	def rpop(self, key):
		return super().rpop(self.make_key(key))

	def llen(self, key):
		return super().llen(self.make_key(key))

	def lrange(self, key, start, stop):
		return super().lrange(self.make_key(key), start, stop)

	def ltrim(self, key, start, stop):
		return super().ltrim(self.make_key(key), start, stop)

	def hset(
		self,
		name: str,
		key: str,
		value,
		shared: bool = False,
		*args,
		**kwargs,
	):
		if key is None:
			return

		_name = self.make_key(name, shared=shared)

		# set in local
		frappe.local.cache.setdefault(_name, {})[key] = value

		# set in redis
		try:
			super().hset(_name, key, pickle.dumps(value, protocol=DEFAULT_PICKLE_PROTOCOL), *args, **kwargs)
		except redis.exceptions.ConnectionError:
			pass

	def hexists(self, name: str, key: str, shared: bool = False) -> bool:
		if key is None:
			return False
		_name = self.make_key(name, shared=shared)
		try:
			return super().hexists(_name, key)
		except redis.exceptions.ConnectionError:
			return False

	def exists(self, *names: str, user=None, shared=None) -> int:
		names = [self.make_key(n, user=user, shared=shared) for n in names]

		try:
			return super().exists(*names)
		except redis.exceptions.ConnectionError:
			return False

	def hgetall(self, name):
		value = super().hgetall(self.make_key(name))
		return {key: pickle.loads(value) for key, value in value.items()}

	def hget(self, name, key, generator=None, shared=False):
		_name = self.make_key(name, shared=shared)

		local_cache = frappe.local.cache
		if _name not in local_cache:
			local_cache[_name] = {}

		if not key:
			return None

		if key in local_cache[_name]:
			return local_cache[_name][key]

		value = None
		try:
			value = super().hget(_name, key)
		except redis.exceptions.ConnectionError:
			pass

		if value is not None:
			value = pickle.loads(value)
			local_cache[_name][key] = value
		elif generator:
			value = generator()
			self.hset(name, key, value, shared=shared)
		return value

	def hdel(
		self,
		name: str,
		keys: str | list | tuple,
		shared=False,
		pipeline: redis.client.Pipeline | None = None,
	):
		"""
		A wrapper around redis' HDEL command

		:param name: The hash name
		:param keys: the keys to delete
		:param shared: shared frappe key or not
		:param pipeline: A redis.client.Pipeline object, if this transaction is to be run in a pipeline
		"""
		_name = self.make_key(name, shared=shared)

		name_in_local_cache = _name in frappe.local.cache

		if not isinstance(keys, list | tuple):
			if name_in_local_cache and keys in frappe.local.cache[_name]:
				del frappe.local.cache[_name][keys]
			if pipeline:
				pipeline.hdel(_name, keys)
			else:
				try:
					super().hdel(_name, keys)
				except redis.exceptions.ConnectionError:
					pass
			return

		local_pipeline = False

		if pipeline is None:
			pipeline = self.pipeline()
			local_pipeline = True

		for key in keys:
			if name_in_local_cache:
				if key in frappe.local.cache[_name]:
					del frappe.local.cache[_name][key]
			pipeline.hdel(_name, key)

		if local_pipeline:
			try:
				pipeline.execute()
			except redis.exceptions.ConnectionError:
				pass

	def hdel_names(self, names: list | tuple, key: str):
		"""
		A function to call HDEL on multiple hash names with a common key, run in a single pipeline

		:param names: The hash names
		:param key: The common key
		"""
		pipeline = self.pipeline()
		for name in names:
			self.hdel(name, key, pipeline=pipeline)
		try:
			pipeline.execute()
		except redis.exceptions.ConnectionError:
			pass

	def hdel_keys(self, name_starts_with, key):
		"""Delete hash names with wildcard `*` and key"""
		pipeline = self.pipeline()
		for name in self.get_keys(name_starts_with):
			name = name.split("|", 1)[1]
			self.hdel(name, key, pipeline=pipeline)
		try:
			pipeline.execute()
		except redis.exceptions.ConnectionError:
			pass

	def hkeys(self, name):
		try:
			return super().hkeys(self.make_key(name))
		except redis.exceptions.ConnectionError:
			return []

	def sadd(self, name, *values):
		"""Add a member/members to a given set"""
		super().sadd(self.make_key(name), *values)

	def srem(self, name, *values):
		"""Remove a specific member/list of members from the set."""
		super().srem(self.make_key(name), *values)

	def sismember(self, name, value):
		"""Return True or False based on if a given value is present in the set."""
		return super().sismember(self.make_key(name), value)

	def spop(self, name):
		"""Remove and returns a random member from the set."""
		return super().spop(self.make_key(name))

	def srandmember(self, name, count=None):
		"""Return a random member from the set."""
		return super().srandmember(self.make_key(name))

	def smembers(self, name):
		"""Return all members of the set."""
		return super().smembers(self.make_key(name))

	def ft(self, index_name="idx"):
		return RedisearchWrapper(client=self, index_name=self.make_key(index_name))


def setup_cache() -> RedisWrapper:
	if frappe.conf.redis_cache_sentinel_enabled:
		sentinels = [tuple(node.split(":")) for node in frappe.conf.get("redis_cache_sentinels", [])]
		sentinel = get_sentinel_connection(
			sentinels=sentinels,
			sentinel_username=frappe.conf.get("redis_cache_sentinel_username"),
			sentinel_password=frappe.conf.get("redis_cache_sentinel_password"),
			master_username=frappe.conf.get("redis_cache_master_username"),
			master_password=frappe.conf.get("redis_cache_master_password"),
		)
		return sentinel.master_for(
			frappe.conf.get("redis_cache_master_service"),
			redis_class=RedisWrapper,
		)

	return RedisWrapper.from_url(frappe.conf.get("redis_cache"))


def get_sentinel_connection(
	sentinels: list[tuple[str, int]],
	sentinel_username=None,
	sentinel_password=None,
	master_username=None,
	master_password=None,
):
	from redis.sentinel import Sentinel

	sentinel_kwargs = {}
	if sentinel_username:
		sentinel_kwargs["username"] = sentinel_username

	if sentinel_password:
		sentinel_kwargs["password"] = sentinel_password

	return Sentinel(
		sentinels=sentinels,
		sentinel_kwargs=sentinel_kwargs,
		username=master_username,
		password=master_password,
	)


class _TrackedConnection(redis.Connection):
	def __init__(self, *args, **kwargs):
		self._invalidator_id = kwargs.pop("_invalidator_id")
		super().__init__(*args, **kwargs)
		# Every redis connection needs to enable client tracking to get notified about invalidated
		# keys.
		self.register_connect_callback(self._enable_client_tracking)

	def _enable_client_tracking(self, conn):
		try:
			conn.send_command("CLIENT", "TRACKING", "ON", "redirect", self._invalidator_id, "NOLOOP")
			conn.read_response()
		except ResponseError as e:
			if "client ID" in str(e) and "does not exist" in str(e):
				# Redis restarted, there's no easy way to recover from this.
				frappe.client_cache.healthy = False
			elif "unknown subcommand" in str(e).lower():
				raise Exception("Redis version is not supported, upgrade to Redis 6.0 or higher.")
			else:
				raise


CachedValue = namedtuple("CachedValue", ["value", "expiry"])
CacheStatistics = namedtuple(
	"CacheStatistics", ["hits", "misses", "capacity", "used", "utilization", "hit_ratio", "healthy"]
)
_PLACEHOLDER_VALUE = CachedValue(value=None, expiry=-1)


class ClientCache:
	"""A subset of RedisWrapper that keeps "local" cache across requests.

	Main reason for doing this is improving performance while reading things like hooks, schema.
	This feature is internal to Frappe Framework and is subjected to change without any notice.
	There aren't many use cases for such aggressive caching outside of core Framework.

	This is an implementation of Redis' "client side caching" concept:
		- https://redis.io/docs/latest/develop/reference/client-side-caching/

	Usage/Notes:
		- Cache keys that do not change often: Think hours-days, not minutes.
		- Cache keys that are read frequently, e.g. every request or at least >10% of the requests.
		- Cache values are not huge, consider avg size of ~4kb per value. You can deviate here and
		  there but not go crazy with caching large values in this cache.
		- We have hardcoded 10 minutes "local" ttl and max 1024 keys.
			You're not supposed to work with these numbers, not change them.
		- Same keys can be accessed with `frappe.cache` too, but that won't implement invalidation.
		- Invalidate things as usual using `delete_value`. Local invalidation should be instant.
		  Do not expect sub-second invalidation guarantees across processes.
		  If you need that kind of guarantees, don't use this cache.
		- When redis connection isn't available or any unknown exceptions are encountered, this
		  cache automatically turns itself off and falls back to behaviour that is equivalent to
		  default Redis cache behaviour.
		- Never use `frappe.cache`'s request local cache along with client-side cache. Two
		  different copies of same key are a big source of data races.
		- This cache uses simple FIFO eviction policy. Make sure your access patterns don't cause
		  the worst case behaviour for this policy. E.g. looping over `maxsize` items repeatedly.
	"""

	def __init__(self, maxsize: int = 1024, ttl=10 * 60, monitor: RedisWrapper | None = None) -> None:
		self.maxsize = maxsize or 1024  # Expect 1024 * 4kb objects ~ 4MB
		self.local_ttl = ttl
		# This guards writes to self.cache, reads are done without a lock.
		self.lock = threading.RLock()
		self.cache: dict[bytes, CachedValue] = {}

		self.invalidator = frappe.cache
		self.healthy = True
		self.connection_retries = 0
		self.invalidator_id = None

		try:
			self.invalidator_id = self.invalidator.client_id()
		except redis.exceptions.ConnectionError:
			# Redis not available, this can happen during setup/startup time
			self.redis = frappe.cache
			self.healthy = False

		# These are local hits and misses, *not* global.
		# - Local miss = not found in worker memory
		# - Global miss = not found in Redis too
		# These stats can be *slightly* off, these aren't guarded by a mutex.
		self.hits = self.misses = 0

		if not self.invalidator_id:
			return

		self.redis: RedisWrapper = RedisWrapper.from_url(
			frappe.conf.get("redis_cache"),
			connection_class=_TrackedConnection,
			_invalidator_id=self.invalidator_id,
			protocol=2,
		)
		self.invalidator_thread = self.run_invalidator_thread()

	def get_value(self, key, *, shared=False, generator=None):
		if not self.healthy:
			return self.redis.get_value(key, shared=shared, generator=generator)

		key = self.redis.make_key(key, shared=shared)
		try:
			val = self.cache[key]
			if time.monotonic() < val.expiry:
				self.hits += 1
				return val.value
		except KeyError:
			pass

		self.misses += 1

		# Store a placeholder value to detect race between GET and parallel invalidation.
		with self.lock:
			self.cache[key] = _PLACEHOLDER_VALUE

		val = self.redis.get_value(key, shared=True, use_local_cache=not self.healthy)

		# Note: We should not "cache" the cache-misses in client cache.
		# This cache is long lived and "misses" are not tracked by redis so they'll never get
		# invalidated.
		if val is None:
			if generator:
				val = generator()
				self.set_value(key, val, shared=True)
				return val
			else:
				return None

		self.ensure_max_size()
		with self.lock:
			# Note: If our placeholder value is not present then it's possible that value we just
			# got is invalidated, so we should not store it in local cache.
			if key in self.cache:
				self.cache[key] = CachedValue(value=val, expiry=time.monotonic() + self.local_ttl)

		return val

	def set_value(self, key, val, *, shared=False):
		key = self.redis.make_key(key, shared=shared)
		self.ensure_max_size()
		self.redis.set_value(key, val, shared=True)
		with self.lock:
			self.cache[key] = CachedValue(value=val, expiry=time.monotonic() + self.local_ttl)
		# XXX: We need to tell redis that we indeed read this key we just wrote
		# This is an edge case:
		# - Client A writes a key and reads it again from local cache
		# - Client B overwrites this key, but since client A never "read" it from Redis, Redis
		#   doesn't send invalidation.
		_ = self.redis.get_value(key, shared=True, use_local_cache=not self.healthy)

	def get_doc(self, doctype: str, name: str | None = None):
		"""Utility to fetch and store documents in client cache.

		Use sparingly, this should ideally be used for settings and doctypes that have few known
		number of documents.
		"""
		if not name:
			name = doctype  # singles
		key = frappe.get_document_cache_key(doctype, name)
		return self.get_value(key, generator=lambda: frappe.get_doc(doctype, name))

	def ensure_max_size(self):
		if len(self.cache) >= self.maxsize:
			with self.lock, suppress(RuntimeError):
				self.cache.pop(next(iter(self.cache)), None)

	def delete_value(self, key, *, shared=False):
		key = self.redis.make_key(key, shared=shared)
		self.redis.delete_value(key, shared=True)
		with self.lock:
			self.cache.pop(key, None)

	def delete_keys(self, pattern):
		keys = self.redis.get_keys(pattern)
		self.redis.delete_value(keys, shared=True, make_keys=False)
		with self.lock:
			for key in keys:
				self.cache.pop(key, None)

	def run_invalidator_thread(self):
		self._watcher = self.invalidator.pubsub()
		self._watcher.subscribe(
			**{
				"__redis__:invalidate": self._handle_invalidation,
				"clear_persistent_cache": self._handle_persistent_cache_invalidation,
			}
		)
		return self._watcher.run_in_thread(
			sleep_time=60,
			daemon=True,
			exception_handler=self._exception_handler,
		)

	def erase_persistent_caches(self, *, doctype=None):
		"""Send signal to clear all worker-specific caches

		This can include cached controller resolution, @site_cache and any other similar persistent
		cache.
		"""
		self.redis.publish(
			"clear_persistent_cache",
			json.dumps({"doctype": doctype, "site": frappe.local.site}),
		)

	def _handle_invalidation(self, message):
		if message["data"] is None:
			# Flushall
			self.clear_cache()
			return
		with self.lock:
			for key in message["data"]:
				self.cache.pop(key, None)

	def _handle_persistent_cache_invalidation(self, message):
		import frappe.utils.caching
		from frappe.cache_manager import clear_controller_cache

		if message["type"] != "message":
			return

		payload = frappe._dict(json.loads(message["data"]))
		clear_controller_cache(payload.doctype, site=payload.site)

		if not payload.doctype:
			frappe.utils.caching._SITE_CACHE.clear()

	def _exception_handler(self, exc, pubsub, pubsub_thread):
		if isinstance(exc, (redis.exceptions.ConnectionError)):
			self.clear_cache()
			self.connection_retries += 1
			if self.connection_retries > 10:
				self.healthy = False
				raise
			time.sleep(1)
		else:
			self.healthy = False
			raise

	def clear_cache(self):
		with self.lock:
			self.cache.clear()

	@property
	def statistics(self) -> CacheStatistics:
		return CacheStatistics(
			hits=self.hits,
			misses=self.misses,
			capacity=self.maxsize,
			used=len(self.cache),
			healthy=self.healthy,
			utilization=round(len(self.cache) / self.maxsize, 2),
			hit_ratio=round(self.hits / (self.hits + self.misses), 2) if self.hits else None,
		)

	def reset_statistics(self):
		self.hits = self.misses = 0
