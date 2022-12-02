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
import time
import unittest

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

import frappe
from frappe.frappeclient import FrappeClient
from frappe.model.base_document import get_controller
from frappe.query_builder.utils import db_type_is
from frappe.tests.test_query_builder import run_only_if
from frappe.tests.utils import FrappeTestCase
from frappe.website.path_resolver import PathResolver


@run_only_if(db_type_is.MARIADB)
class TestPerformance(FrappeTestCase):
	def reset_request_specific_caches(self):
		# To simulate close to request level of handling
		frappe.destroy()  # releases everything on frappe.local
		frappe.init(site=self.TEST_SITE)
		frappe.connect()
		frappe.clear_cache()

	def setUp(self) -> None:
		self.HOST = frappe.utils.get_site_url(frappe.local.site)

		self.reset_request_specific_caches()

	def test_meta_caching(self):
		frappe.get_meta("User")

		with self.assertQueryCount(0):
			frappe.get_meta("User")

	def test_set_value_query_count(self):
		frappe.db.set_value("User", "Administrator", "interest", "Nothing")

		with self.assertQueryCount(1):
			frappe.db.set_value("User", "Administrator", "interest", "Nothing")

		with self.assertQueryCount(1):
			frappe.db.set_value("User", {"user_type": "System User"}, "interest", "Nothing")

		with self.assertQueryCount(1):
			frappe.db.set_value(
				"User", {"user_type": "System User"}, {"interest": "Nothing", "bio": "boring person"}
			)

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

	@retry(
		retry=retry_if_exception_type(AssertionError),
		stop=stop_after_attempt(3),
		wait=wait_fixed(0.5),
		reraise=True,
	)
	def test_req_per_seconds_basic(self):
		"""Ideally should be ran against gunicorn worker, though I have not seen any difference
		when using werkzeug's run_simple for synchronous requests."""

		EXPECTED_RPS = 50  # measured on GHA
		FAILURE_THREASHOLD = 0.1

		req_count = 1000
		client = FrappeClient(self.HOST, "Administrator", self.ADMIN_PASSWORD)

		start = time.perf_counter()
		for _ in range(req_count):
			client.get_list("ToDo", limit_page_length=1)
		end = time.perf_counter()

		rps = req_count / (end - start)

		print(f"Completed {req_count} in {end - start} @ {rps} requests per seconds")
		self.assertGreaterEqual(
			rps,
			EXPECTED_RPS * (1 - FAILURE_THREASHOLD),
			f"Possible performance regression in basic /api/Resource list  requests",
		)

	@unittest.skip("Not implemented")
	def test_homepage_resolver(self):
		paths = ["/", "/app"]
		for path in paths:
			PathResolver(path).resolve()
			with self.assertQueryCount(1):
				PathResolver(path).resolve()
