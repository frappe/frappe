#  -*- coding: utf-8 -*-

# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe

from frappe.tasks import run_async_task

class TestAsync(unittest.TestCase):

	def test_response(self):
		result = run_async_task(frappe.local.site, 'Administrator', 'async_ping', frappe._dict())
		self.assertEquals(result.message, "pong")
