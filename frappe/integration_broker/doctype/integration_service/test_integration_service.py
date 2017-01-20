# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
from frappe.utils.scheduler import get_scheduler_events

# test_records = frappe.get_test_records('Integration Service')

class TestIntegrationService(unittest.TestCase):
	def test_scheudler_events(self):
		if not frappe.db.exists("Integration Service", "Dropbox"):
			frappe.get_doc({
				"doctype": "Integration Service",
				"service": "Dropbox"
			}).insert(ignore_permissions=True)

		frappe.db.set_value("Integration Service", "Dropbox", "enabled", 1)
		frappe.cache().delete_key('scheduler_events')
		events = get_scheduler_events('daily_long')

		self.assertTrue('frappe.integrations.doctype.dropbox_settings.dropbox_settings.take_backups_daily' in events)

		frappe.db.set_value("Integration Service", "Dropbox", "enabled", 0)
