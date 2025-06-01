# Copyright (c) 2020, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import time

from werkzeug.wrappers import Response

import nts
import nts.rate_limiter
from nts.rate_limiter import RateLimiter
from nts.tests.utils import ntsTestCase
from nts.utils import cint


class TestRateLimiter(ntsTestCase):
	def test_apply_with_limit(self):
		nts.conf.rate_limit = {"window": 86400, "limit": 1}
		nts.rate_limiter.apply()

		self.assertTrue(hasattr(nts.local, "rate_limiter"))
		self.assertIsInstance(nts.local.rate_limiter, RateLimiter)

		nts.cache.delete(nts.local.rate_limiter.key)
		delattr(nts.local, "rate_limiter")

	def test_apply_without_limit(self):
		nts.conf.rate_limit = None
		nts.rate_limiter.apply()

		self.assertFalse(hasattr(nts.local, "rate_limiter"))

	def test_respond_over_limit(self):
		limiter = RateLimiter(1, 86400)
		time.sleep(1)
		limiter.update()

		nts.conf.rate_limit = {"window": 86400, "limit": 1}
		self.assertRaises(nts.TooManyRequestsError, nts.rate_limiter.apply)
		nts.rate_limiter.update()

		response = nts.rate_limiter.respond()

		self.assertIsInstance(response, Response)
		self.assertEqual(response.status_code, 429)

		headers = nts.local.rate_limiter.headers()
		self.assertIn("Retry-After", headers)
		self.assertIn("X-RateLimit-Reset", headers)
		self.assertIn("X-RateLimit-Limit", headers)
		self.assertIn("X-RateLimit-Remaining", headers)
		self.assertTrue(int(headers["X-RateLimit-Reset"]) <= 86400)
		self.assertEqual(int(headers["X-RateLimit-Limit"]), 1000000)
		self.assertEqual(int(headers["X-RateLimit-Remaining"]), 0)

		nts.cache.delete(limiter.key)
		nts.cache.delete(nts.local.rate_limiter.key)
		delattr(nts.local, "rate_limiter")

	def test_respond_under_limit(self):
		nts.conf.rate_limit = {"window": 86400, "limit": 0.01}
		nts.rate_limiter.apply()
		nts.rate_limiter.update()
		response = nts.rate_limiter.respond()
		self.assertEqual(response, None)

		nts.cache.delete(nts.local.rate_limiter.key)
		delattr(nts.local, "rate_limiter")

	def test_headers_under_limit(self):
		nts.conf.rate_limit = {"window": 86400, "limit": 1}
		nts.rate_limiter.apply()
		nts.rate_limiter.update()
		headers = nts.local.rate_limiter.headers()
		self.assertNotIn("Retry-After", headers)
		self.assertIn("X-RateLimit-Reset", headers)
		self.assertTrue(int(headers["X-RateLimit-Reset"] < 86400))
		self.assertEqual(int(headers["X-RateLimit-Limit"]), 1000000)
		self.assertEqual(int(headers["X-RateLimit-Remaining"]), 1000000)

		nts.cache.delete(nts.local.rate_limiter.key)
		delattr(nts.local, "rate_limiter")

	def test_reject_over_limit(self):
		limiter = RateLimiter(0.01, 86400)
		time.sleep(0.01)
		limiter.update()

		limiter = RateLimiter(0.01, 86400)
		self.assertRaises(nts.TooManyRequestsError, limiter.apply)

		nts.cache.delete(limiter.key)

	def test_do_not_reject_under_limit(self):
		limiter = RateLimiter(0.01, 86400)
		time.sleep(0.01)
		limiter.update()

		limiter = RateLimiter(0.02, 86400)
		self.assertEqual(limiter.apply(), None)

		nts.cache.delete(limiter.key)

	def test_update_method(self):
		limiter = RateLimiter(0.01, 86400)
		time.sleep(0.01)
		limiter.update()

		self.assertEqual(limiter.duration, cint(nts.cache.get(limiter.key)))

		nts.cache.delete(limiter.key)

	def test_window_expires(self):
		limiter = RateLimiter(1000, 1)
		self.assertTrue(nts.cache.exists(limiter.key, shared=True))
		limiter.update()
		self.assertTrue(nts.cache.exists(limiter.key, shared=True))
		time.sleep(1.1)
		self.assertFalse(nts.cache.exists(limiter.key, shared=True))
		nts.cache.delete(limiter.key)
