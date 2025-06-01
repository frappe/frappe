# Copyright (c) 2020, nts Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import nts
import nts.monitor
from nts.monitor import MONITOR_REDIS_KEY, get_trace_id
from nts.tests.utils import ntsTestCase
from nts.utils import set_request
from nts.utils.response import build_response


class TestMonitor(ntsTestCase):
	def setUp(self):
		nts.conf.monitor = 1
		nts.cache.delete_value(MONITOR_REDIS_KEY)

	def tearDown(self):
		nts.conf.monitor = 0
		nts.cache.delete_value(MONITOR_REDIS_KEY)

	def test_enable_monitor(self):
		set_request(method="GET", path="/api/method/nts.ping")
		response = build_response("json")

		nts.monitor.start()
		nts.monitor.stop(response)

		logs = nts.cache.lrange(MONITOR_REDIS_KEY, 0, -1)
		self.assertEqual(len(logs), 1)

		log = nts.parse_json(logs[0].decode())
		self.assertTrue(log.duration)
		self.assertTrue(log.site)
		self.assertTrue(log.timestamp)
		self.assertTrue(log.uuid)
		self.assertTrue(log.request)
		self.assertEqual(log.transaction_type, "request")
		self.assertEqual(log.request["method"], "GET")

	def test_no_response(self):
		set_request(method="GET", path="/api/method/nts.ping")

		nts.monitor.start()
		nts.monitor.stop(response=None)

		logs = nts.cache.lrange(MONITOR_REDIS_KEY, 0, -1)
		self.assertEqual(len(logs), 1)

		log = nts.parse_json(logs[0].decode())
		self.assertEqual(log.request["status_code"], 500)
		self.assertEqual(log.transaction_type, "request")
		self.assertEqual(log.request["method"], "GET")

	def test_job(self):
		nts.utils.background_jobs.execute_job(
			nts.local.site, "nts.ping", None, None, {}, is_async=False
		)

		logs = nts.cache.lrange(MONITOR_REDIS_KEY, 0, -1)
		self.assertEqual(len(logs), 1)
		log = nts.parse_json(logs[0].decode())
		self.assertEqual(log.transaction_type, "job")
		self.assertTrue(log.job)
		self.assertEqual(log.job["method"], "nts.ping")
		self.assertEqual(log.job["scheduled"], False)
		self.assertEqual(log.job["wait"], 0)

	def test_flush(self):
		set_request(method="GET", path="/api/method/nts.ping")
		response = build_response("json")
		nts.monitor.start()
		nts.monitor.stop(response)

		open(nts.monitor.log_file(), "w").close()
		nts.monitor.flush()

		with open(nts.monitor.log_file()) as f:
			logs = f.readlines()

		self.assertEqual(len(logs), 1)
		log = nts.parse_json(logs[0])
		self.assertEqual(log.transaction_type, "request")

	def test_trace_ids(self):
		set_request(method="GET", path="/api/method/nts.ping")
		response = build_response("json")
		nts.monitor.start()
		nts.db.sql("select 1")
		self.assertIn(get_trace_id(), str(nts.db.last_query))
		nts.monitor.stop(response)
