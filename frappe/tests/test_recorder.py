# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import time

import sqlparse

import frappe
import frappe.recorder
from frappe.recorder import normalize_query
from frappe.tests import IntegrationTestCase, timeout
from frappe.utils import set_request
from frappe.utils.doctor import any_job_pending
from frappe.website.serve import get_response_content


class TestRecorder(IntegrationTestCase):
	def setUp(self):
		self.wait_for_background_jobs()
		frappe.recorder.stop()
		frappe.recorder.delete()
		set_request()
		frappe.recorder.start()
		frappe.recorder.record()

	@timeout
	def wait_for_background_jobs(self):
		while any_job_pending(frappe.local.site):
			time.sleep(1)

	def stop_recording(self):
		frappe.recorder.dump()
		frappe.recorder.stop()

	def test_start(self):
		self.stop_recording()
		requests = frappe.recorder.get()
		self.assertEqual(len(requests), 1)

	def test_do_not_record(self):
		frappe.recorder.do_not_record(frappe.get_all)("DocType")
		self.stop_recording()
		requests = frappe.recorder.get()
		self.assertEqual(len(requests), 0)

	def test_get(self):
		self.stop_recording()

		requests = frappe.recorder.get()
		self.assertEqual(len(requests), 1)

		request = frappe.recorder.get(requests[0]["uuid"])
		self.assertTrue(request)

	def test_delete(self):
		self.stop_recording()

		requests = frappe.recorder.get()
		self.assertEqual(len(requests), 1)

		frappe.recorder.delete()

		requests = frappe.recorder.get()
		self.assertEqual(len(requests), 0)

	def test_record_without_sql_queries(self):
		self.stop_recording()

		requests = frappe.recorder.get()
		request = frappe.recorder.get(requests[0]["uuid"])

		self.assertEqual(len(request["calls"]), 0)

	def test_record_with_sql_queries(self):
		frappe.get_all("DocType")
		self.stop_recording()

		requests = frappe.recorder.get()
		request = frappe.recorder.get(requests[0]["uuid"])

		self.assertNotEqual(len(request["calls"]), 0)

	def test_explain(self):
		frappe.db.sql("SELECT * FROM tabDocType")
		frappe.db.sql("COMMIT")
		frappe.db.sql("select 1", run=0)
		self.stop_recording()

		requests = frappe.recorder.get()
		request = frappe.recorder.get(requests[0]["uuid"])

		self.assertEqual(len(request["calls"][0]["explain_result"]), 1)
		self.assertEqual(len(request["calls"][1]["explain_result"]), 0)

	def test_multiple_queries(self):
		queries = [
			{"mariadb": "SELECT * FROM tabDocType", "postgres": 'SELECT * FROM "tabDocType"'},
			{"mariadb": "SELECT COUNT(*) FROM tabDocType", "postgres": 'SELECT COUNT(*) FROM "tabDocType"'},
			{"mariadb": "COMMIT", "postgres": "COMMIT"},
		]

		sql_dialect = frappe.db.db_type or "mariadb"
		for query in queries:
			frappe.db.sql(query[sql_dialect])

		self.stop_recording()

		requests = frappe.recorder.get()
		request = frappe.recorder.get(requests[0]["uuid"])

		self.assertEqual(len(request["calls"]), len(queries))

		for query, call in zip(queries, request["calls"], strict=False):
			self.assertEqual(
				call["query"],
				sqlparse.format(
					query[sql_dialect].strip(), keyword_case="upper", reindent=True, strip_comments=True
				),
			)

	def test_duplicate_queries(self):
		queries = [
			("SELECT * FROM tabDocType", 2),
			("SELECT COUNT(*) FROM tabDocType", 1),
			("select * from tabDocType", 2),
			("COMMIT", 3),
			("COMMIT", 3),
			("COMMIT", 3),
		]
		for query in queries:
			frappe.db.sql(query[0])

		self.stop_recording()

		requests = frappe.recorder.get()
		request = frappe.recorder.get(requests[0]["uuid"])

		for query, call in zip(queries, request["calls"], strict=False):
			self.assertEqual(call["exact_copies"], query[1])

	def test_error_page_rendering(self):
		content = get_response_content("error")
		self.assertIn("Error", content)


class TestRecorderDeco(IntegrationTestCase):
	def test_recorder_flag(self):
		frappe.recorder.delete()

		@frappe.recorder.record_queries
		def test():
			frappe.get_all("User")

		test()
		self.assertTrue(frappe.recorder.get())


class TestQueryNormalization(IntegrationTestCase):
	def test_query_normalization(self):
		test_cases = {
			"select * from user where name = 'x'": "select * from user where name = ?",
			"select * from user where a > 5": "select * from user where a > ?",
			"select * from `user` where a > 5": "select * from `user` where a > ?",
			"select `name` from `user`": "select `name` from `user`",
			"select `name` from `user` limit 10": "select `name` from `user` limit ?",
			"select `name` from `user` where name in ('a', 'b', 'c')": "select `name` from `user` where name in (?)",
		}

		for query, normalized in test_cases.items():
			self.assertEqual(normalize_query(query), normalized)
