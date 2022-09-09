"""
This file contains multiple primitive tests for avoiding performance regressions.

- Time bound tests: Benchmarks are done on GHA before adding numbers
- Query count tests: More than expected # of queries for any action is frequent source of
  performance issues. This guards against such problems.


E.g. We know get_controller is supposed to be cached and hence shouldn't make query post first
query. This test can be written like this.

>>> def test_controller_caching(self):
>>>
>>> 	get_controller("User")  # <- "warm up code"
>>> 	with self.assertQueryCount(0):
>>> 		get_controller("User")

"""
import unittest

import frappe
from frappe.model.base_document import get_controller
from frappe.tests.utils import FrappeTestCase
from frappe.website.path_resolver import PathResolver


class TestPerformance(FrappeTestCase):
	def reset_request_specific_caches(self):
		# To simulate close to request level of handling
		frappe.destroy()  # releases everything on frappe.local
		frappe.init(site=self.TEST_SITE)
		frappe.connect()
		frappe.clear_cache()

	def setUp(self) -> None:
		self.reset_request_specific_caches()

	def test_meta_caching(self):
		frappe.get_meta("User")

		with self.assertQueryCount(0):
			frappe.get_meta("User")

	def test_controller_caching(self):

		get_controller("User")
		with self.assertQueryCount(0):
			get_controller("User")

	def test_db_value_cache(self):
		"""Link validation if repeated should just use db.value_cache, hence no extra queries"""
		doc = frappe.get_last_doc("User")
		doc.get_invalid_links()

		with self.assertQueryCount(0):
			doc.get_invalid_links()

	@unittest.skip("Not implemented")
	def test_homepage_resolver(self):
		paths = ["/", "/app"]
		for path in paths:
			PathResolver(path).resolve()
			with self.assertQueryCount(1):
				PathResolver(path).resolve()
