import time
from unittest.mock import MagicMock

import frappe
from frappe.tests.test_api import FrappeAPITestCase
from frappe.tests.utils import FrappeTestCase
from frappe.utils.caching import redis_cache, request_cache, site_cache

CACHE_TTL = 4
external_service = MagicMock(return_value=30)
register_with_external_service = MagicMock(return_value=True)


@request_cache
def request_specific_api(a: list | tuple | dict | int, b: int) -> int:
	# API that takes very long to return a result
	todays_value = external_service()
	if not isinstance(a, (int, float)):
		a = 1
	return a**b * todays_value


@frappe.whitelist(allow_guest=True)
@site_cache
def ping() -> str:
	register_with_external_service(frappe.local.site)
	return frappe.local.site


@frappe.whitelist(allow_guest=True)
@site_cache(ttl=CACHE_TTL)
def ping_with_ttl() -> str:
	register_with_external_service(frappe.local.site)
	return frappe.local.site


class TestCachingUtils(FrappeTestCase):
	def test_request_cache(self):
		retval = []
		acceptable_args = [
			[1, 2, 3, 4],
			range(10),
			{"abc": "test-key"},
			frappe.get_last_doc("DocType"),
			frappe._dict(),
		]
		same_output_received = lambda: all([x for x in set(retval) if x == retval[0]])

		# ensure that external service was called only once
		# thereby return value of request_specific_api is cached
		for _ in range(5):
			retval.append(request_specific_api(120, 23))
		external_service.assert_called_once()
		self.assertTrue(same_output_received())

		# ensure that cache differentiates between int & float
		# types. Giving different return values for both
		retval.append(request_specific_api(120.0, 23))
		self.assertTrue(external_service.call_count, 2)

		# ensure that function is executed when call isn't
		# already cached
		retval.clear()
		for _ in range(10):
			request_specific_api(120, 13)
		self.assertTrue(external_service.call_count, 3)
		self.assertTrue(same_output_received())

		# ensure key generation capacity for different types
		retval.clear()
		for arg in acceptable_args:
			external_service.call_count = 0
			for _ in range(2):
				request_specific_api(arg, 13)
			self.assertTrue(external_service.call_count, 1)
		self.assertTrue(same_output_received())


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

		time.sleep(CACHE_TTL)
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
