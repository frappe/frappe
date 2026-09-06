import time

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils.redis_wrapper import ClientCache

TEST_KEY = "42"


class TestClientCache(IntegrationTestCase):
	def setUp(self) -> None:
		frappe.client_cache.delete_value(TEST_KEY)
		return super().setUp()

	def test_client_cache_is_used(self):
		frappe.client_cache.set_value(TEST_KEY, 42)
		frappe.client_cache.get_value(TEST_KEY)
		with self.assertRedisCallCounts(0):
			frappe.client_cache.get_value(TEST_KEY)

	def test_client_cache_is_updated_instantly_noloop(self):
		val = frappe.generate_hash()
		frappe.client_cache.set_value(TEST_KEY, val)
		with self.assertRedisCallCounts(0):  # Locally set value should not be invalidated.
			self.assertEqual(frappe.client_cache.get_value(TEST_KEY), val)

	def test_invalidation_from_another_client_works(self):
		frappe.client_cache.reset_statistics()
		val = frappe.generate_hash()
		frappe.client_cache.set_value(TEST_KEY, val)
		self.assertEqual(frappe.client_cache.get_value(TEST_KEY), val)

		# frappe.cache is our "another client"
		val = frappe.generate_hash()
		frappe.cache.set_value(TEST_KEY, val)
		# This is almost instant, but obviously not as fast as running the next instruction in
		# current thread. So we wait.
		time.sleep(0.1)

		with self.assertRedisCallCounts(1, exact=True):
			self.assertEqual(frappe.client_cache.get_value(TEST_KEY), val)

		self.assertEqual(frappe.client_cache.statistics.hits, 1)
		self.assertEqual(frappe.client_cache.statistics.misses, 1)
		self.assertEqual(frappe.client_cache.statistics.hit_ratio, 0.5)

	def test_delete_invalidates(self):
		val = frappe.generate_hash()
		frappe.client_cache.set_value(TEST_KEY, val)
		self.assertEqual(frappe.client_cache.get_value(TEST_KEY), val)

		val = frappe.generate_hash()
		frappe.cache.delete_value(TEST_KEY)
		# This is almost instant, but obviously not as fast as running the next instruction in
		# current thread. So we wait.
		time.sleep(0.1)

		with self.assertRedisCallCounts(1, exact=True):
			self.assertIsNone(frappe.client_cache.get_value(TEST_KEY))

		# Flushall should have results
		frappe.client_cache.set_value(TEST_KEY, val)
		self.assertEqual(frappe.client_cache.get_value(TEST_KEY), val)
		frappe.cache.flushall()
		time.sleep(0.1)
		with self.assertRedisCallCounts(1, exact=True):
			self.assertIsNone(frappe.client_cache.get_value(TEST_KEY))

		# frappe.clear_cache should have same results
		frappe.client_cache.set_value(TEST_KEY, val)
		self.assertEqual(frappe.client_cache.get_value(TEST_KEY), val)
		frappe.clear_cache()
		time.sleep(0.1)
		with self.assertRedisCallCounts(1, exact=True):
			self.assertIsNone(frappe.client_cache.get_value(TEST_KEY))

	def test_client_local_cache_ttl(self):
		c = ClientCache(ttl=1)
		c.set_value(TEST_KEY, 42)
		with self.assertRedisCallCounts(0):
			c.get_value(TEST_KEY)
		time.sleep(1)

		with self.assertRedisCallCounts(1, exact=True):
			c.get_value(TEST_KEY)

	def test_client_cache_maxsize(self):
		c = ClientCache(maxsize=2)
		c.set_value(TEST_KEY, 42)
		c.set_value(frappe.generate_hash(), 42)
		c.set_value(frappe.generate_hash(), 42)

		self.assertEqual(len(c.cache), 2)

	def test_client_cache_maxsize_bytes(self):
		c = ClientCache(maxsize_bytes=50_000)
		for _ in range(10):
			c.set_value(frappe.generate_hash(), "z" * 10_000)

		self.assertLessEqual(c._total_size, 50_000 + 10_100)
		self.assertEqual(c._total_size, sum(e.size for e in c.cache.values()))

	def test_client_cache_no_byte_limit_by_default(self):
		c = ClientCache()
		for _ in range(10):
			c.set_value(frappe.generate_hash(), "z" * 10_000)

		self.assertEqual(c.maxsize_bytes, 0)
		self.assertEqual(len(c.cache), 10)

	def test_client_cache_size_accounting(self):
		c = ClientCache()
		key = frappe.generate_hash()

		c.set_value(key, "z" * 10_000)
		self.assertEqual(c._total_size, sum(e.size for e in c.cache.values()))

		# overwriting must not double count
		c.set_value(key, "z" * 10_000)
		self.assertEqual(c._total_size, sum(e.size for e in c.cache.values()))

		c.delete_value(key)
		self.assertEqual(c._total_size, sum(e.size for e in c.cache.values()))

	@staticmethod
	def _expire_entries(cache: ClientCache) -> None:
		"""Put every entry past its ttl, without a wait on the clock."""
		with cache.lock:
			for key, entry in cache.cache.items():
				cache.cache[key] = entry._replace(expiry=time.monotonic() - 1)

	def test_client_cache_size_not_leaked_on_expiry(self):
		"""An expired entry is replaced by a placeholder, its size must be released."""
		c = ClientCache()
		key = frappe.generate_hash()
		c.set_value(key, "z" * 10_000)

		for _ in range(3):
			self._expire_entries(c)
			c.get_value(key)
			self.assertEqual(c._total_size, sum(e.size for e in c.cache.values()))

	def test_shared_keyspace(self):
		val = frappe.generate_hash()
		frappe.client_cache.set_value(TEST_KEY, val)

		self.assertEqual(frappe.client_cache.get_value(TEST_KEY), frappe.cache.get_value(TEST_KEY))

	def test_shared_keys(self):
		val = frappe.generate_hash()
		frappe.client_cache.set_value(TEST_KEY, val, shared=True)
		with self.assertRedisCallCounts(0):
			self.assertEqual(frappe.client_cache.get_value(TEST_KEY, shared=True), val)

	def test_generator(self):
		val = frappe.generate_hash()
		with self.assertRedisCallCounts(3, exact=True):
			self.assertEqual(frappe.client_cache.get_value(TEST_KEY, generator=lambda: val), val)

		with self.assertRedisCallCounts(0):
			self.assertEqual(frappe.client_cache.get_value(TEST_KEY, generator=lambda: val), val)

	def test_get_doc(self):
		frappe.client_cache.get_doc("User", "Guest")
		with self.assertRedisCallCounts(0):
			frappe.client_cache.get_doc("User", "Guest")
