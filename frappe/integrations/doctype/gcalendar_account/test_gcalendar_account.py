# -*- coding: utf-8 -*-
# Copyright (c) 2018, DOKOS and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

class TestGCalendarAccount(unittest.TestCase):
	def test_create_connector(self):
		users = frappe.get_all("User")
		doc = frappe.new_doc("GCalendar Account")
		doc.enabled = 1
		doc.user = users[0].name
		doc.calendar_name = "Frappe Test"
		doc.save()
		self.assertTrue(frappe.db.exists('GCalendar Account', users[0].name))

		connector_name = 'Calendar Connector-' + users[0].name
		self.assertTrue(frappe.db.exists('Data Migration Connector', connector_name))
