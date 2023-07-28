# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import sqlparse

import frappe
import frappe.recorder
from frappe.recorder import normalize_query
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.website.serve import get_response_content


class TestRecorder(FrappeTestCase):
	def setUp(self):
		frappe.recorder.stop()
		frappe.recorder.delete()
		set_request()
		frappe.recorder.start()
		frappe.recorder.record()

	def test_start(self):
		frappe.recorder.dump()
		requests = frappe.recorder.get()
		self.assertEqual(len(requests), 1)

	def test_do_not_record(self):
		frappe.recorder.do_not_record(frappe.get_all)("DocType")
		frappe.recorder.dump()
		requests = frappe.recorder.get()
		self.assertEqual(len(requests), 0)

	def test_get(self):
		frappe.recorder.dump()

		requests = frappe.recorder.get()
		self.assertEqual(len(requests), 1)

		request = frappe.recorder.get(requests[0]["uuid"])
		self.assertTrue(request)

	def test_delete(self):
		frappe.recorder.dump()

		requests = frappe.recorder.get()
		self.assertEqual(len(requests), 1)

		frappe.recorder.delete()

		requests = frappe.recorder.get()
		self.assertEqual(len(requests), 0)

	def test_record_without_sql_queries(self):
		frappe.recorder.dump()

		requests = frappe.recorder.get()
		request = frappe.recorder.get(requests[0]["uuid"])

		self.assertEqual(len(request["calls"]), 0)

	def test_record_with_sql_queries(self):
		frappe.get_all("DocType")
		frappe.recorder.dump()

		requests = frappe.recorder.get()
		request = frappe.recorder.get(requests[0]["uuid"])

		self.assertNotEqual(len(request["calls"]), 0)

	def test_explain(self):
		frappe.db.sql("SELECT * FROM tabDocType")
		frappe.db.sql("COMMIT")
		frappe.recorder.dump()
		frappe.recorder.post_process()

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

		frappe.recorder.dump()
		frappe.recorder.post_process()

		requests = frappe.recorder.get()
		request = frappe.recorder.get(requests[0]["uuid"])

		self.assertEqual(len(request["calls"]), len(queries))

		for query, call in zip(queries, request["calls"]):
			self.assertEqual(
				call["query"], sqlparse.format(query[sql_dialect].strip(), keyword_case="upper", reindent=True)
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

		frappe.recorder.dump()
		frappe.recorder.post_process()

		requests = frappe.recorder.get()
		request = frappe.recorder.get(requests[0]["uuid"])

		for query, call in zip(queries, request["calls"]):
			self.assertEqual(call["exact_copies"], query[1])

	def test_error_page_rendering(self):
		content = get_response_content("error")
		self.assertIn("Error", content)


class TestRecorderDeco(FrappeTestCase):
	def test_recorder_flag(self):
		frappe.recorder.delete()

		@frappe.recorder.record_queries
		def test():
			frappe.get_all("User")

		test()
		self.assertTrue(frappe.recorder.get())


class TestQueryNormalization(FrappeTestCase):
	def test_query_normalization(self):
		test_cases = {
			"select * from user where name = 'x'": "select * from user where name = ?",
			"select * from user where a > 5": "select * from user where a > ?",
			"select * from `user` where a > 5": "select * from `user` where a > ?",
			"select `name` from `user`": "select `name` from `user`",
			"select `name` from `user` limit 10": "select `name` from `user` limit ?",
		}

		for query, normalized in test_cases.items():
			self.assertEqual(normalize_query(query), normalized)
