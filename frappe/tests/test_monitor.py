#  -*- coding: utf-8 -*-
<<<<<<< HEAD
<<<<<<< HEAD
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
=======
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
>>>>>>> af3c4feb64 (feat: Monitor)
=======
# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
>>>>>>> 4740e4f7e6 (refactor: Monitor)
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe
import frappe.monitor
<<<<<<< HEAD
from frappe.tests import set_request
from frappe.utils.response import build_response
from frappe.monitor import MONITOR_REDIS_KEY
=======
from frappe.utils import set_request
from frappe.utils.response import build_response
from frappe.monitor import MONITOR_REDIS_KEY
<<<<<<< HEAD
import json
>>>>>>> af3c4feb64 (feat: Monitor)
=======
>>>>>>> 4e69326fac (style: Remove unused imports)


class TestMonitor(unittest.TestCase):
	def setUp(self):
		frappe.conf.monitor = 1
		frappe.cache().delete_value(MONITOR_REDIS_KEY)

	def test_enable_monitor(self):
<<<<<<< HEAD
<<<<<<< HEAD
		set_request(method="GET", path="/api/method/frappe.ping")
		response = build_response("json")

		frappe.monitor.start()
		frappe.monitor.stop(response)

		logs = frappe.cache().lrange(MONITOR_REDIS_KEY, 0, -1)
		self.assertEqual(len(logs), 1)

		log = frappe.parse_json(logs[0].decode())
		self.assertTrue(log.duration)
		self.assertTrue(log.site)
		self.assertTrue(log.timestamp)
		self.assertTrue(log.uuid)
		self.assertTrue(log.request)
		self.assertEqual(log.transaction_type, "request")
		self.assertEqual(log.request["method"], "GET")

	def test_job(self):
		frappe.utils.background_jobs.execute_job(
			frappe.local.site, "frappe.ping", None, None, {}, is_async=False
		)

		logs = frappe.cache().lrange(MONITOR_REDIS_KEY, 0, -1)
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
=======
		set_request()
=======
		set_request(method="GET", path="/api/method/frappe.ping")
		response = build_response("json")

>>>>>>> 4740e4f7e6 (refactor: Monitor)
		frappe.monitor.start()
		frappe.monitor.stop(response)

		logs = frappe.cache().lrange(MONITOR_REDIS_KEY, 0, -1)
		self.assertEqual(len(logs), 1)

<<<<<<< HEAD
	def test_flush(self):
		set_request()
		frappe.monitor.start()
		frappe.monitor.stop()
>>>>>>> af3c4feb64 (feat: Monitor)

		open(frappe.monitor.log_file(), "w").close()
		frappe.monitor.flush()

		with open(frappe.monitor.log_file()) as f:
			logs = f.readlines()

		self.assertEqual(len(logs), 1)
<<<<<<< HEAD
		log = frappe.parse_json(logs[0])
		self.assertEqual(log.transaction_type, "request")
=======
		log = json.loads(logs[0])
		self.assertEqual(log["transaction_type"], "request")
=======
		log = frappe.parse_json(logs[0].decode())
		self.assertTrue(log.duration)
		self.assertTrue(log.site)
		self.assertTrue(log.timestamp)
		self.assertTrue(log.uuid)
		self.assertTrue(log.request)
		self.assertEqual(log.transaction_type, "request")
		self.assertEqual(log.request["method"], "GET")

		# Reponse body will be set as "{}"
		self.assertEqual(log.request["response_length"], 2)
		self.assertEqual(log.request["status_code"], 200)
>>>>>>> 4740e4f7e6 (refactor: Monitor)

	def test_job(self):
		frappe.utils.background_jobs.execute_job(
			frappe.local.site, "frappe.ping", None, None, {}, is_async=False
		)

		logs = frappe.cache().lrange(MONITOR_REDIS_KEY, 0, -1)
		self.assertEqual(len(logs), 1)
<<<<<<< HEAD
		log = json.loads(logs[0].decode())
		self.assertEqual(log["transaction_type"], "job")
		self.assertEqual(log["method"], "frappe.ping")
>>>>>>> af3c4feb64 (feat: Monitor)
=======
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
>>>>>>> 4740e4f7e6 (refactor: Monitor)

	def tearDown(self):
		frappe.conf.monitor = 0
		frappe.cache().delete_value(MONITOR_REDIS_KEY)
