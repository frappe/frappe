import time
from unittest.mock import MagicMock, patch

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.tests import IntegrationTestCase
from frappe.tests.test_api import FrappeAPITestCase
from frappe.tests.utils import whitelist_for_tests
from frappe.utils.caching import redis_cache, request_cache, site_cache

CACHE_TTL = 4
external_service = MagicMock(return_value=30)
register_with_external_service = MagicMock(return_value=True)


@request_cache
def request_specific_api(a: list | tuple | dict | int, b: int) -> int:
	# API that takes very long to return a result
	todays_value = external_service()
	if not isinstance(a, int | float):
		a = 1
	return a**b * todays_value


@whitelist_for_tests(allow_guest=True)
@site_cache
def ping() -> str:
	register_with_external_service(frappe.local.site)
	return "pong"


@whitelist_for_tests(allow_guest=True)
@site_cache(ttl=CACHE_TTL)
def ping_with_ttl() -> str:
	register_with_external_service(frappe.local.site)
	return "pong"


class TestCachingUtils(IntegrationTestCase):
	def test_request_cache(self):
		retval = []
		hashable_values = [
			range(10),
			frappe.get_last_doc("DocType"),
			True,
			None,
		]

		unhashable_values = [
			[1, 2, 3, 4],
			{"abc": "test-key"},
			frappe._dict(),
		]

		def same_output_received():
			return len(set(retval)) == 1

		# ensure that external service was called only once
		# thereby return value of request_specific_api is cached
		retval.extend(request_specific_api(120, 23) for _ in range(5))
		external_service.assert_called_once()
		self.assertTrue(same_output_received())

		# hash() function does not differentiate between int & float
		# Giving same values for both
		retval.append(request_specific_api(120.0, 23))
		external_service.assert_called_once()
		self.assertTrue(same_output_received())

		# ensure that function is executed when call isn't already cached
		retval.clear()
		retval.extend(request_specific_api(120, 13) for _ in range(10))
		self.assertEqual(external_service.call_count, 2)
		self.assertTrue(same_output_received())

		# ensure single call if key is hashable
		for arg in hashable_values:
			external_service.reset_mock()
			for _ in range(2):
				request_specific_api(arg, 13)

			self.assertEqual(external_service.call_count, 1)

		# multiple calls if key cannot be generated
		for arg in unhashable_values:
			external_service.reset_mock()
			for _ in range(2):
				request_specific_api(arg, 13)

			self.assertEqual(external_service.call_count, 2)


class TestSiteCache(FrappeAPITestCase):
	def test_site_cache(self):
		module = __name__
		api_with_ttl = f"{module}.ping_with_ttl"
		api_without_ttl = f"{module}.ping"

		for _ in range(5):
			self.get(f"/api/method/{api_with_ttl}")
			self.get(f"/api/method/{api_without_ttl}")

		self.assertEqual(register_with_external_service.call_count, 2)
		time.sleep(CACHE_TTL)
		self.get(f"/api/method/{api_with_ttl}")
		self.assertEqual(register_with_external_service.call_count, 3)


class TestRedisCache(FrappeAPITestCase):
	def test_redis_cache(self):
		function_call_count = 0

		@redis_cache(ttl=CACHE_TTL)
		def calculate_area(radius: float) -> float:
			nonlocal function_call_count
			function_call_count += 1
			return 3.14 * radius**2

		self.assertEqual(calculate_area(10), 314)
		self.assertEqual(function_call_count, 1)
		self.assertEqual(calculate_area(10), 314)
		self.assertEqual(function_call_count, 1)

		time.sleep(CACHE_TTL * 1.5)
		frappe.local.cache.clear()
		self.assertEqual(calculate_area(10), 314)
		self.assertEqual(function_call_count, 2)

		calculate_area.clear_cache()
		self.assertEqual(calculate_area(10), 314)
		self.assertEqual(function_call_count, 3)
		calculate_area.clear_cache()

	def test_redis_cache_without_params(self):
		function_call_count = 0

		@redis_cache
		def calculate_area(radius: float) -> float:
			nonlocal function_call_count
			function_call_count += 1
			return 3.14 * radius**2

		calculate_area.clear_cache()
		self.assertEqual(calculate_area(10), 314)
		self.assertEqual(function_call_count, 1)

		calculate_area.clear_cache()
		self.assertEqual(calculate_area(10), 314)
		self.assertEqual(function_call_count, 2)

		calculate_area.clear_cache()

	def test_redis_cache_diff_args(self):
		function_call_count = 0

		@redis_cache(ttl=CACHE_TTL)
		def calculate_area(radius: float) -> float:
			nonlocal function_call_count
			function_call_count += 1
			return 3.14 * radius**2

		self.assertEqual(calculate_area(10), 314)
		self.assertEqual(function_call_count, 1)
		self.assertEqual(calculate_area(100), 31400)
		self.assertEqual(function_call_count, 2)

		self.assertEqual(calculate_area(5), 25 * 3.14)
		self.assertEqual(function_call_count, 3)

		calculate_area(10)
		# from cache now
		self.assertEqual(function_call_count, 3)

		calculate_area(radius=10)
		# args, kwargs are treated differently
		self.assertEqual(function_call_count, 4)

		calculate_area(radius=10)
		# kwargs should hit cache too
		self.assertEqual(function_call_count, 4)

	def test_global_clear_cache(self):
		function_call_count = 0

		@redis_cache()
		def calculate_area(radius: float) -> float:
			nonlocal function_call_count
			function_call_count += 1
			return 3.14 * radius**2

		calculate_area(10)
		calculate_area(10)
		calculate_area(10)
		self.assertEqual(function_call_count, 1)

		# This is supposed to clear cache for the active site
		frappe.clear_cache()
		calculate_area(10)
		self.assertEqual(function_call_count, 2)

	def test_user_cache(self):
		function_call_count = 0
		PI = 3.1415
		ENGINEERING_PI = _E = 3

		@redis_cache(user=True)
		def calculate_area(radius: float) -> float:
			nonlocal function_call_count
			PI_APPROX = ENGINEERING_PI if frappe.session.user == "Engineer" else PI
			function_call_count += 1
			return PI_APPROX * radius**2

		with self.set_user("Engineer"):
			self.assertEqual(calculate_area(1), ENGINEERING_PI)
			self.assertEqual(function_call_count, 1)

		with self.set_user("Mathematician"):
			self.assertEqual(calculate_area(1), PI)
			self.assertEqual(function_call_count, 2)

		with self.set_user("Engineer"):
			self.assertEqual(calculate_area(1), ENGINEERING_PI)
			self.assertEqual(function_call_count, 2)

		with self.set_user("Mathematician"):
			self.assertEqual(calculate_area(1), PI)
			self.assertEqual(function_call_count, 2)


class TestDocumentCache(FrappeAPITestCase):
	TEST_DOCTYPE = "User"
	TEST_DOCNAME = "Administrator"
	TEST_FIELD = "middle_name"

	def setUp(self) -> None:
		self.test_value = frappe.generate_hash()

	def test_caching(self):
		frappe.get_cached_doc(self.TEST_DOCTYPE, self.TEST_DOCNAME)

		with self.assertQueryCount(0):
			doc = frappe.get_cached_doc(self.TEST_DOCTYPE, self.TEST_DOCNAME)

		doc.db_set(self.TEST_FIELD, self.test_value)
		new_doc = frappe.get_cached_doc(self.TEST_DOCTYPE, self.TEST_DOCNAME)

		self.assertIsNot(doc, new_doc)  # Shouldn't be same object from frappe.local
		self.assertEqual(new_doc.get(self.TEST_FIELD), self.test_value)  # Cache invalidated and fetched
		frappe.db.rollback()

		doc_after_rollback = frappe.get_cached_doc(self.TEST_DOCTYPE, self.TEST_DOCNAME)
		self.assertIsNot(new_doc, doc_after_rollback)
		# Cache invalidated after rollback
		self.assertNotEqual(doc_after_rollback.get(self.TEST_FIELD), self.test_value)

		with self.assertQueryCount(0):
			frappe.get_cached_doc(self.TEST_DOCTYPE, self.TEST_DOCNAME)

	def test_cache_invalidation_set_value(self):
		doc = frappe.get_cached_doc(self.TEST_DOCTYPE, self.TEST_DOCNAME)

		frappe.db.set_value(
			self.TEST_DOCTYPE,
			{"name": ("like", "%Admin%")},
			self.TEST_FIELD,
			self.test_value,
		)

		new_doc = frappe.get_cached_doc(self.TEST_DOCTYPE, self.TEST_DOCNAME)
		self.assertIsNot(doc, new_doc)
		self.assertEqual(new_doc.get(self.TEST_FIELD), self.test_value)

		with self.assertQueryCount(0):
			frappe.get_cached_doc(self.TEST_DOCTYPE, self.TEST_DOCNAME)


class TestRedisWrapper(FrappeAPITestCase):
	def test_delete_keys(self):
		prefix = "test_del_"

		for i in range(5):
			frappe.cache.set_value(f"{prefix}{i}", 1)

		self.assertEqual(len(frappe.cache.get_keys(prefix)), 5)
		frappe.cache.delete_keys(prefix)
		self.assertEqual(len(frappe.cache.get_keys(prefix)), 0)

	def test_delete_keys_with_user_and_shared_args(self):
		user_prefix = "test_user_del_"
		shared_prefix = "test_shared_del_"

		for i in range(3):
			frappe.cache.set_value(f"{user_prefix}{i}", 1, user="Administrator")
			frappe.cache.set_value(f"{shared_prefix}{i}", 1, shared=True)

		self.assertEqual(len(frappe.cache.get_keys(user_prefix, user="Administrator")), 3)
		self.assertEqual(len(frappe.cache.get_keys(shared_prefix, shared=True)), 3)

		frappe.cache.delete_keys(user_prefix, user="Administrator")
		frappe.cache.delete_keys(shared_prefix, shared=True)

		self.assertEqual(len(frappe.cache.get_keys(user_prefix, user="Administrator")), 0)
		self.assertEqual(len(frappe.cache.get_keys(shared_prefix, shared=True)), 0)

	def test_hash(self):
		key = "test_hash"

		# Confirm that there's no data initially
		exists = frappe.cache.exists(key)
		self.assertFalse(exists)

		# Insert 5 key-value pairs
		for i in range(5):
			frappe.cache.hset(key, f"key_{i}", f"value_{i}")

		# Check that we have 5 values
		values = frappe.cache.hgetall(key)
		self.assertEqual(len(values), 5)

		# Check that each value matches
		for i in range(5):
			value = frappe.cache.hget(key, f"key_{i}")
			self.assertEqual(value, f"value_{i}")

		# Check the keys themselves
		keys = frappe.cache.hkeys(key)
		for i in range(5):
			self.assertIn(f"key_{i}".encode(), keys)

		# Delete a single key and check that we still have the remaining 4
		frappe.cache.hdel(key, "key_1")
		values = frappe.cache.hgetall(key)
		self.assertEqual(len(values), 4)

		# Delete 2 keys and check that we still have the remaining 2
		frappe.cache.hdel(key, ["key_2", "key_3"])
		values = frappe.cache.hgetall(key)
		self.assertEqual(len(values), 2)

		# Delete the hash itself and confirm that there's no data
		frappe.cache.delete_value(key)
		exists = frappe.cache.exists(key)
		self.assertFalse(exists)

	def test_user_cache_clear(self):
		from frappe.cache_manager import user_cache_keys

		# Set some keys that a user's cache would usually have
		user1 = frappe.utils.random_string(10)
		user2 = frappe.utils.random_string(10)
		for key in user_cache_keys:
			frappe.cache.hset(key, user1, key)
			frappe.cache.hset(key, user2, key)

		frappe.clear_cache(user=user1)

		# Check that the keys for user1 are gone
		for key in set(user_cache_keys) - {"home_page"}:
			self.assertFalse(frappe.cache.hexists(key, user1))
			self.assertTrue(frappe.cache.hexists(key, user2))

	def test_doctype_cache_clear(self):
		from frappe.cache_manager import doctype_cache_keys

		# Set some keys that a user's cache would usually have
		doctype1 = new_doctype(frappe.utils.random_string(10))
		doctype2 = new_doctype(frappe.utils.random_string(10))
		for key in doctype_cache_keys:
			frappe.cache.hset(key, doctype1.name, key)
			frappe.cache.hset(key, doctype2.name, key)

		frappe.clear_cache(doctype=doctype1.name)

		# Check that the keys for doctype1 are gone
		for key in doctype_cache_keys:
			self.assertFalse(frappe.cache.hexists(key, doctype1.name))
			self.assertTrue(frappe.cache.hexists(key, doctype2.name))

	def test_backward_compat_cache(self):
		self.assertEqual(frappe.cache, frappe.cache())

	def test_cache_fallback_on_redis_failure(self):
		"""Test that cache falls back to memory cache when Redis connection fails"""
		import redis

		from frappe.utils.redis_wrapper import MemoryCacheWrapper, setup_cache

		with patch("frappe.utils.redis_wrapper.RedisWrapper.from_url") as mock_from_url:
			mock_from_url.side_effect = redis.exceptions.ConnectionError("Redis connection failed")

			with patch.object(
				frappe.local,
				"conf",
				type(
					"conf",
					(),
					{
						"get": lambda self, key, default=None: None,
						"redis_cache_sentinel_enabled": False,
					},
				)(),
			):
				cache = setup_cache()
				self.assertIsInstance(
					cache, MemoryCacheWrapper, "Should fall back to MemoryCacheWrapper when Redis fails"
				)

	def test_memory_cache_operations(self):
		"""Test that MemoryCacheWrapper works for basic cache operations"""
		from frappe.utils.redis_wrapper import MemoryCacheWrapper

		cache = MemoryCacheWrapper()

		# Test basic set/get
		cache.set_value("test_key", "test_value")
		self.assertEqual(cache.get_value("test_key"), "test_value")

		# Test hash operations
		cache.hset("hash_key", "field1", "value1")
		cache.hset("hash_key", "field2", "value2")
		self.assertEqual(cache.hget("hash_key", "field1"), "value1")
		self.assertEqual(cache.hgetall("hash_key"), {"field1": "value1", "field2": "value2"})

		# Test list operations
		cache.lpush("list_key", "item1")
		cache.lpush("list_key", "item2")
		self.assertEqual(cache.lrange("list_key", 0, -1), ["item2", "item1"])
		self.assertEqual(cache.lpop("list_key"), "item2")

		# Test delete operations
		cache.delete_value("test_key")
		self.assertIsNone(cache.get_value("test_key"))

	def test_memory_cache_exports_and_configured_backend(self):
		from frappe.utils import redis_wrapper
		from frappe.utils.memory_cache import MemoryCacheWrapper, MemoryPipeline
		from frappe.utils.redis_wrapper import setup_cache

		self.assertIs(redis_wrapper.MemoryCacheWrapper, MemoryCacheWrapper)
		self.assertIs(redis_wrapper.MemoryPipeline, MemoryPipeline)

		with self.assertRaises(AttributeError):
			redis_wrapper.__getattr__("UnknownCache")

		with patch.object(
			frappe.local,
			"conf",
			type(
				"conf",
				(),
				{
					"get": lambda self, key, default=None: {"use_memory_cache": True}.get(key, default),
					"redis_cache_sentinel_enabled": False,
				},
			)(),
		):
			cache = setup_cache()
			self.assertIsInstance(cache, MemoryCacheWrapper)

	def test_setup_cache_uses_sentinel_when_available(self):
		from frappe.utils.redis_wrapper import setup_cache

		redis_cache = MagicMock()
		redis_cache.connected.return_value = True
		sentinel = MagicMock()
		sentinel.master_for.return_value = redis_cache

		with (
			patch("frappe.utils.redis_wrapper.get_sentinel_connection", return_value=sentinel),
			patch.object(
				frappe.local,
				"conf",
				type(
					"conf",
					(),
					{
						"get": lambda self, key, default=None: {
							"redis_cache_sentinels": ["localhost:26379"],
							"redis_cache_master_service": "mymaster",
						}.get(key, default),
						"redis_cache_sentinel_enabled": True,
					},
				)(),
			),
		):
			cache = setup_cache()

		self.assertIs(cache, redis_cache)
		sentinel.master_for.assert_called_once()

	def test_setup_cache_sentinel_falls_back_on_failed_connection_test(self):
		from frappe.utils.memory_cache import MemoryCacheWrapper
		from frappe.utils.redis_wrapper import setup_cache

		redis_cache = MagicMock()
		redis_cache.connected.return_value = False
		sentinel = MagicMock()
		sentinel.master_for.return_value = redis_cache

		with (
			patch("frappe.utils.redis_wrapper.get_sentinel_connection", return_value=sentinel),
			patch.object(
				frappe.local,
				"conf",
				type(
					"conf",
					(),
					{
						"get": lambda self, key, default=None: {
							"redis_cache_sentinels": ["localhost:26379"],
							"redis_cache_master_service": "mymaster",
						}.get(key, default),
						"redis_cache_sentinel_enabled": True,
					},
				)(),
			),
		):
			cache = setup_cache()

		self.assertIsInstance(cache, MemoryCacheWrapper)

	def test_cache_fallback_on_unexpected_redis_setup_error(self):
		from frappe.utils.memory_cache import MemoryCacheWrapper
		from frappe.utils.redis_wrapper import setup_cache

		with patch("frappe.utils.redis_wrapper.RedisWrapper.from_url") as mock_from_url:
			mock_from_url.side_effect = RuntimeError("unexpected failure")

			with patch.object(
				frappe.local,
				"conf",
				type(
					"conf",
					(),
					{
						"get": lambda self, key, default=None: None,
						"redis_cache_sentinel_enabled": False,
					},
				)(),
			):
				cache = setup_cache()
				self.assertIsInstance(cache, MemoryCacheWrapper)

	def test_memory_cache_key_and_expiry_operations(self):
		from frappe.utils.memory_cache import MemoryCacheWrapper

		cache = MemoryCacheWrapper()
		frappe.local.cache.clear()

		self.assertIs(cache(), cache)
		self.assertTrue(cache.ping())
		self.assertTrue(cache.connected())
		self.assertEqual(cache.client_id(), 1)
		self.assertEqual(cache.execute_command("INFO"), {})

		cache.set_value("plain", "value")
		self.assertEqual(cache.get_value("plain"), "value")
		self.assertEqual(cache.exists("plain"), 1)

		generator_calls = 0

		def generate_value():
			nonlocal generator_calls
			generator_calls += 1
			return "generated"

		self.assertEqual(cache.get_value("generated", generator=generate_value), "generated")
		self.assertEqual(cache.get_value("generated", generator=generate_value), "generated")
		self.assertEqual(generator_calls, 1)

		cache.set_value("user-key", "user-value", user="Administrator")
		cache.set_value("shared-key", "shared-value", shared=True)
		self.assertEqual(cache.get_value("user-key", user="Administrator"), "user-value")
		self.assertEqual(cache.get_value("shared-key", shared=True), "shared-value")
		self.assertEqual(cache.exists("user-key", user="Administrator"), 1)
		self.assertEqual(cache.exists("shared-key", shared=True), 1)
		self.assertEqual(len(cache.get_keys("user-", user="Administrator")), 1)
		self.assertEqual(len(cache.get_keys("shared-", shared=True)), 1)

		cache.delete_keys("user-", user="Administrator")
		cache.delete_keys("shared-", shared=True)
		self.assertEqual(cache.exists("user-key", user="Administrator"), 0)
		self.assertEqual(cache.exists("shared-key", shared=True), 0)

		with patch("frappe.utils.memory_cache.time.time", side_effect=[100, 100, 102]):
			cache.set_value("expiring", "soon-gone", expires_in_sec=1)
			frappe.local.cache.pop(cache.make_key("expiring"), None)
			self.assertEqual(cache.get_value("expiring", use_local_cache=False), "soon-gone")
			frappe.local.cache.pop(cache.make_key("expiring"), None)
			self.assertIsNone(cache.get_value("expiring", use_local_cache=False))

		cache.set_value("delete-me", "gone")
		cache.delete_key("delete-me")
		self.assertEqual(cache.exists("delete-me"), 0)

		self.assertTrue(cache.expire_key("plain", 10))
		self.assertIn(cache.make_key("plain"), cache.expiries)

	def test_memory_cache_collection_operations(self):
		from frappe.utils.memory_cache import MemoryCacheWrapper

		cache = MemoryCacheWrapper()
		frappe.local.cache.clear()

		cache.lpush("queue", "first")
		cache.rpush("queue", "second")
		cache.lpush("queue", "zero")
		self.assertEqual(cache.llen("queue"), 3)
		self.assertEqual(cache.lrange("queue", 0, -1), ["zero", "first", "second"])
		self.assertEqual(cache.blpop("queue"), "zero")
		self.assertEqual(cache.rpop("queue"), "second")
		cache.rpush("queue", "third")
		cache.ltrim("queue", 1, -1)
		self.assertEqual(cache.lrange("queue", 0, -1), ["third"])
		with patch("frappe.utils.memory_cache.time.sleep") as sleep:
			self.assertIsNone(cache.blpop("missing", timeout=1))
			sleep.assert_called_once_with(1)

		cache.hset("hash", "field1", "value1")
		self.assertEqual(cache.hget("hash", "field1"), "value1")
		self.assertEqual(cache.hget("hash", "field2", generator=lambda: "value2"), "value2")
		self.assertEqual(set(cache.hkeys("hash")), {"field1", "field2"})
		self.assertEqual(cache.hgetall("hash"), {"field1": "value1", "field2": "value2"})
		self.assertTrue(cache.hexists("hash", "field1"))
		self.assertFalse(cache.hexists("hash", None))
		cache.hdel("hash", "field1")
		self.assertFalse(cache.hexists("hash", "field1"))

		cache.hset("prefix:first", "shared-field", "one")
		cache.hset("prefix:second", "shared-field", "two")
		cache.hdel_keys("prefix:", "shared-field")
		self.assertFalse(cache.hexists("prefix:first", "shared-field"))
		self.assertFalse(cache.hexists("prefix:second", "shared-field"))

		cache.hset("hash-one", "name", "one")
		cache.hset("hash-two", "name", "two")
		cache.hdel_names(["hash-one", "hash-two"], "name")
		self.assertFalse(cache.hexists("hash-one", "name"))
		self.assertFalse(cache.hexists("hash-two", "name"))

		cache.sadd("letters", "a", "b", "c")
		self.assertTrue(cache.sismember("letters", "a"))
		self.assertEqual(cache.smembers("letters"), {"a", "b", "c"})
		self.assertIn(cache.srandmember("letters"), {"a", "b", "c"})
		self.assertEqual(len(cache.srandmember("letters", 2)), 2)
		popped = cache.spop("letters")
		self.assertNotIn(popped, cache.smembers("letters"))
		cache.srem("letters", "b")
		self.assertFalse(cache.sismember("letters", "b"))

		results = (
			cache.pipeline().set_value("pipe-key", "pipe").hset("pipe-hash", "k", "v").missing().execute()
		)
		self.assertEqual(results, [None, None])
		self.assertEqual(cache.get_value("pipe-key"), "pipe")
		self.assertEqual(cache.hget("pipe-hash", "k"), "v")

		self.assertEqual(cache.incrby("counter"), 1)
		self.assertEqual(cache.incrby("counter", 3), 4)
		self.assertTrue(cache.expire("counter", 5))
		self.assertIn("counter", cache.expiries)

		pubsub = cache.pubsub()
		self.assertIsNone(pubsub.subscribe(channel="updates"))
		self.assertTrue(pubsub.run_in_thread().is_alive())


class TestHttpCache(FrappeAPITestCase):
	def test_http_headers(self):
		resp = self.get(
			self.method("frappe.client.is_document_amended"),
			{"sid": self.sid, "doctype": "User", "docname": "Guest"},
		)
		self.assertEqual(resp.cache_control.max_age, 600)
		self.assertTrue(resp.cache_control.private)
