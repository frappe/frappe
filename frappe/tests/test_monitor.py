# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
import frappe.monitor
from frappe.monitor import MONITOR_REDIS_KEY, get_trace_id
from frappe.tests.utils import FrappeTestCase
from frappe.utils import set_request
from frappe.utils.response import build_response


class TestMonitor(FrappeTestCase):
	def setUp(self):
		frappe.conf.monitor = 1
		frappe.cache.delete_value(MONITOR_REDIS_KEY)

	def tearDown(self):
		frappe.conf.monitor = 0
		frappe.cache.delete_value(MONITOR_REDIS_KEY)

	def test_enable_monitor(self):
		set_request(method="GET", path="/api/method/frappe.ping")
		response = build_response("json")

		frappe.monitor.start()
		frappe.monitor.stop(response)

		logs = frappe.cache.lrange(MONITOR_REDIS_KEY, 0, -1)
		self.assertEqual(len(logs), 1)

		log = frappe.parse_json(logs[0].decode())
		self.assertTrue(log.duration)
		self.assertTrue(log.site)
		self.assertTrue(log.timestamp)
		self.assertTrue(log.uuid)
		self.assertTrue(log.request)
		self.assertEqual(log.transaction_type, "request")
		self.assertEqual(log.request["method"], "GET")

	def test_no_response(self):
		set_request(method="GET", path="/api/method/frappe.ping")

		frappe.monitor.start()
		frappe.monitor.stop(response=None)

		logs = frappe.cache.lrange(MONITOR_REDIS_KEY, 0, -1)
		self.assertEqual(len(logs), 1)

		log = frappe.parse_json(logs[0].decode())
		self.assertEqual(log.request["status_code"], 500)
		self.assertEqual(log.transaction_type, "request")
		self.assertEqual(log.request["method"], "GET")

	def test_job(self):
		frappe.utils.background_jobs.execute_job(
			frappe.local.site, "frappe.ping", None, None, {}, is_async=False
		)

		logs = frappe.cache.lrange(MONITOR_REDIS_KEY, 0, -1)
		self.assertEqual(len(logs), 1)
		log = frappe.parse_json(logs[0].decode())
		self.assertEqual(log.transaction_type, "job")
		self.assertTrue(log.job)
		self.assertEqual(log.job["method"], "frappe.ping")
		self.assertEqual(log.job["scheduled"], False)
		self.assertEqual(log.job["wait"], 0)

	def test_flush(self):
		set_request(method="GET", path="/api/method/frappe.ping")
		response = build_response("json")
		frappe.monitor.start()
		frappe.monitor.stop(response)

		open(frappe.monitor.log_file(), "w").close()
		frappe.monitor.flush()

		with open(frappe.monitor.log_file()) as f:
			logs = f.readlines()

		self.assertEqual(len(logs), 1)
		log = frappe.parse_json(logs[0])
		self.assertEqual(log.transaction_type, "request")

	def test_trace_ids(self):
		set_request(method="GET", path="/api/method/frappe.ping")
		response = build_response("json")
		frappe.monitor.start()
		frappe.db.sql("select 1")
		self.assertIn(get_trace_id(), str(frappe.db.last_query))
		frappe.monitor.stop(response)

	def test_trace_id_rejects_unsafe_header(self):
		"""A request ID that doesn't match the expected format must be ignored."""
		malformed = "*/ or sleep(0) -- "
		set_request(method="GET", path="/api/method/frappe.ping", headers={"X-Frappe-Request-Id": malformed})
		response = build_response("json")
		frappe.monitor.start()
		frappe.db.sql("select 1")

		self.assertNotIn(malformed, str(frappe.db.last_query))
		self.assertTrue(frappe.monitor.TRACE_ID_PATTERN.fullmatch(get_trace_id()))
		frappe.monitor.stop(response)

	def test_trace_id_accepts_valid_header(self):
		"""A request ID matching the expected format is passed through as-is."""
		request_id = "7f037421-6b54-4ee6-8c8a-e7698f67b7a5"
		set_request(method="GET", path="/api/method/frappe.ping", headers={"X-Frappe-Request-Id": request_id})
		response = build_response("json")
		frappe.monitor.start()
		frappe.db.sql("select 1")

		self.assertEqual(get_trace_id(), request_id)
		self.assertIn(request_id, str(frappe.db.last_query))
		frappe.monitor.stop(response)
