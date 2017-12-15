# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

class TestWebhook(unittest.TestCase):
	def test_validate_docevents(self):
		doc = frappe.new_doc("Webhook")
		doc.webhook_doctype = "User"
		doc.webhook_docevent = "on_submit"
		doc.request_url = "https://httpbin.org/post"
		self.assertRaises(frappe.ValidationError, doc.save)
	def test_validate_request_url(self):
		doc = frappe.new_doc("Webhook")
		doc.webhook_doctype = "User"
		doc.webhook_docevent = "after_insert"
		doc.request_url = "httpbin.org?post"
		self.assertRaises(frappe.ValidationError, doc.save)
