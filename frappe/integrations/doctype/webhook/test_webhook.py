# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

class TestWebhook(unittest.TestCase):
	def test_mandatory_fields(self):
		base_doc = frappe.new_doc("Webhook")
		
		# Test for scheduler event webhook
		scheduler_event_doc = base_doc
		scheduler_event_doc.webhook_type = "Scheduler Event"
		self.assertRaises(frappe.ValidationError, scheduler_event_doc.save)

		# Test for doc event webhook
		doc_event_doc = base_doc
		doc_event_doc.webhook_type = "Doc Event"
		self.assertRaises(frappe.ValidationError, doc_event_doc.save)
