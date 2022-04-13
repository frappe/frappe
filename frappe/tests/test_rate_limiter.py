#  -*- coding: utf-8 -*-

# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import time
import unittest

from werkzeug.wrappers import Response

import frappe
import frappe.rate_limiter
from frappe.rate_limiter import RateLimiter
from frappe.utils import cint


class TestRateLimiter(unittest.TestCase):
	def setUp(self):
		pass

	def test_apply_with_limit(self):
		frappe.conf.rate_limit = {"window": 86400, "limit": 1}
		frappe.rate_limiter.apply()

		self.assertTrue(hasattr(frappe.local, "rate_limiter"))
		self.assertIsInstance(frappe.local.rate_limiter, RateLimiter)

		frappe.cache().delete(frappe.local.rate_limiter.key)
		delattr(frappe.local, "rate_limiter")

	def test_apply_without_limit(self):
		frappe.conf.rate_limit = None
		frappe.rate_limiter.apply()

		self.assertFalse(hasattr(frappe.local, "rate_limiter"))

	def test_respond_over_limit(self):
		limiter = RateLimiter(0.01, 86400)
		time.sleep(0.01)
		limiter.update()

		frappe.conf.rate_limit = {"window": 86400, "limit": 0.01}
		self.assertRaises(frappe.TooManyRequestsError, frappe.rate_limiter.apply)
		frappe.rate_limiter.update()

		response = frappe.rate_limiter.respond()

		self.assertIsInstance(response, Response)
		self.assertEqual(response.status_code, 429)

		headers = frappe.local.rate_limiter.headers()
		self.assertIn("Retry-After", headers)
		self.assertNotIn("X-RateLimit-Used", headers)
		self.assertIn("X-RateLimit-Reset", headers)
		self.assertIn("X-RateLimit-Limit", headers)
		self.assertIn("X-RateLimit-Remaining", headers)
		self.assertTrue(int(headers["X-RateLimit-Reset"]) <= 86400)
		self.assertEqual(int(headers["X-RateLimit-Limit"]), 10000)
		self.assertEqual(int(headers["X-RateLimit-Remaining"]), 0)

		frappe.cache().delete(limiter.key)
		frappe.cache().delete(frappe.local.rate_limiter.key)
		delattr(frappe.local, "rate_limiter")

	def test_respond_under_limit(self):
		frappe.conf.rate_limit = {"window": 86400, "limit": 0.01}
		frappe.rate_limiter.apply()
		frappe.rate_limiter.update()
		response = frappe.rate_limiter.respond()
		self.assertEqual(response, None)

		frappe.cache().delete(frappe.local.rate_limiter.key)
		delattr(frappe.local, "rate_limiter")

	def test_headers_under_limit(self):
		frappe.conf.rate_limit = {"window": 86400, "limit": 0.01}
		frappe.rate_limiter.apply()
		frappe.rate_limiter.update()
		headers = frappe.local.rate_limiter.headers()
		self.assertNotIn("Retry-After", headers)
		self.assertIn("X-RateLimit-Reset", headers)
		self.assertTrue(int(headers["X-RateLimit-Reset"] < 86400))
		self.assertEqual(int(headers["X-RateLimit-Used"]), frappe.local.rate_limiter.duration)
		self.assertEqual(int(headers["X-RateLimit-Limit"]), 10000)
		self.assertEqual(int(headers["X-RateLimit-Remaining"]), 10000)

		frappe.cache().delete(frappe.local.rate_limiter.key)
		delattr(frappe.local, "rate_limiter")

	def test_reject_over_limit(self):
		limiter = RateLimiter(0.01, 86400)
		time.sleep(0.01)
		limiter.update()

		limiter = RateLimiter(0.01, 86400)
		self.assertRaises(frappe.TooManyRequestsError, limiter.apply)

		frappe.cache().delete(limiter.key)

	def test_do_not_reject_under_limit(self):
		limiter = RateLimiter(0.01, 86400)
		time.sleep(0.01)
		limiter.update()

		limiter = RateLimiter(0.02, 86400)
		self.assertEqual(limiter.apply(), None)

		frappe.cache().delete(limiter.key)

	def test_update_method(self):
		limiter = RateLimiter(0.01, 86400)
		time.sleep(0.01)
		limiter.update()

		self.assertEqual(limiter.duration, cint(frappe.cache().get(limiter.key)))

		frappe.cache().delete(limiter.key)
