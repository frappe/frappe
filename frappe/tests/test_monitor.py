#  -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe
import frappe.monitor
from frappe.utils import set_request
from frappe.monitor import MONITOR_REDIS_KEY
import json


class TestMonitor(unittest.TestCase):
	def setUp(self):
		frappe.conf.monitor = 1
		frappe.cache().delete_value(MONITOR_REDIS_KEY)

	def test_enable_monitor(self):
		set_request()
		frappe.monitor.start()
		frappe.monitor.stop()

		logs = frappe.cache().lrange(MONITOR_REDIS_KEY, 0, -1)
		self.assertEqual(len(logs), 1)
		log = json.loads(logs[0].decode())
		self.assertEqual(log["transaction_type"], "request")

	def test_flush(self):
		set_request()
		frappe.monitor.start()
		frappe.monitor.stop()

		open(frappe.monitor.log_file(), "w").close()
		frappe.monitor.flush()

		with open(frappe.monitor.log_file()) as f:
			logs = f.readlines()

		self.assertEqual(len(logs), 1)
		log = json.loads(logs[0])
		self.assertEqual(log["transaction_type"], "request")

	def test_job(self):
		frappe.utils.background_jobs.execute_job(
			frappe.local.site, "frappe.ping", None, None, {}, is_async=False
		)

		logs = frappe.cache().lrange(MONITOR_REDIS_KEY, 0, -1)
		self.assertEqual(len(logs), 1)
		log = json.loads(logs[0].decode())
		self.assertEqual(log["transaction_type"], "job")
		self.assertEqual(log["method"], "frappe.ping")

	def tearDown(self):
		frappe.conf.monitor = 0
		frappe.cache().delete_value(MONITOR_REDIS_KEY)
