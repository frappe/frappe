# Copyright (c) 2023, Frappe Technologies and Contributors
# See license.txt

import re

import frappe
import frappe.recorder
from frappe.core.doctype.recorder.recorder import _optimize_query, serialize_request
from frappe.query_builder.utils import db_type_is
from frappe.recorder import get as get_recorder_data
from frappe.tests.test_query_builder import run_only_if
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request


class TestRecorder(FrappeTestCase):
	def setUp(self):
		self.start_recoder()

	def tearDown(self) -> None:
		frappe.recorder.stop()

	def start_recoder(self):
		frappe.recorder.stop()
		frappe.recorder.delete()
		set_request(path="/api/method/ping")
		frappe.recorder.start()
		frappe.recorder.record()

	def stop_recorder(self):
		frappe.recorder.dump()

	def test_recorder_list(self):
		frappe.get_all("User")  # trigger one query
		self.stop_recorder()
		requests = frappe.get_all("Recorder")
		self.assertGreaterEqual(len(requests), 1)
		request = frappe.get_doc("Recorder", requests[0].name)
		self.assertGreaterEqual(len(request.sql_queries), 1)
		queries = [sql_query.query for sql_query in request.sql_queries]
		match_flag = 0
		for query in queries:
			if bool(re.match("^[select.*from `tabUser`]", query, flags=re.IGNORECASE)):
				match_flag = 1
				break
		self.assertEqual(match_flag, 1)

	def test_recorder_list_filters(self):
		user = frappe.qb.DocType("User")
		frappe.qb.from_(user).select("name").run()
		self.stop_recorder()

		set_request(path="/api/method/abc")
		frappe.recorder.start()
		frappe.recorder.record()
		frappe.get_all("User")
		self.stop_recorder()

		requests = frappe.get_list(
			"Recorder", filters={"path": ("like", "/api/method/ping"), "number_of_queries": 1}
		)
		self.assertGreaterEqual(len(requests), 1)
		requests = frappe.get_list("Recorder", filters={"path": ("like", "/api/method/test")})
		self.assertEqual(len(requests), 0)

		requests = frappe.get_list("Recorder", filters={"method": "GET"})
		self.assertGreaterEqual(len(requests), 1)
		requests = frappe.get_list("Recorder", filters={"method": "POST"})
		self.assertEqual(len(requests), 0)

		requests = frappe.get_list("Recorder", order_by="path desc")
		self.assertEqual(requests[0].path, "/api/method/ping")

	def test_recorder_serialization(self):
		frappe.get_all("User")  # trigger one query
		self.stop_recorder()
		requests = frappe.get_all("Recorder")
		request_doc = get_recorder_data(requests[0].name)
		self.assertIsInstance(serialize_request(request_doc), dict)

	def test_recorder_doc_events_timeline(self):
		# saving a document runs its lifecycle methods through Document.run_method,
		# which the recorder should capture as a timeline of events.
		frappe.get_doc(doctype="ToDo", description="recorder timeline test").insert()
		self.stop_recorder()

		requests = frappe.get_all("Recorder")
		self.assertGreaterEqual(len(requests), 1)
		request = frappe.get_doc("Recorder", requests[0].name)

		self.assertGreaterEqual(len(request.timeline), 1)
		self.assertEqual(request.number_of_events, len(request.timeline))

		methods = {event.method for event in request.timeline}
		lifecycle = {"before_insert", "validate", "before_save", "after_insert", "on_update"}
		self.assertTrue(
			methods & lifecycle,
			msg=f"expected lifecycle methods in timeline, got: {methods}",
		)

		event = request.timeline[0]
		self.assertTrue(event.method)
		self.assertGreaterEqual(event.duration, 0)
		self.assertGreaterEqual(event.queries, 0)

	def test_timeline_can_be_disabled(self):
		frappe.recorder.stop()
		frappe.recorder.delete()
		set_request(path="/api/method/ping")
		frappe.recorder.start(capture_doc_events=False)
		frappe.recorder.record()
		frappe.get_doc(doctype="ToDo", description="no timeline").insert()
		self.stop_recorder()

		request = frappe.get_doc("Recorder", frappe.get_all("Recorder")[0].name)
		self.assertEqual(len(request.timeline), 0)


class TestQueryOptimization(FrappeTestCase):
	@run_only_if(db_type_is.MARIADB)
	def test_query_optimizer(self):
		suggested_index = _optimize_query(
			"""select name from
			`tabUser` u
			join `tabHas Role` r
			on r.parent = u.name
			where email='xyz'
			and modified > '2023'
			and bio like '%xyz%'
			"""
		)
		self.assertEqual(suggested_index.table, "tabUser")
		self.assertEqual(suggested_index.column, "email")
