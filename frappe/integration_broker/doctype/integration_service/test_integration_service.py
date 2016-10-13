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
		dropbox_settings = frappe.get_doc('Dropbox Settings')
		dropbox_settings.db_set('enabled', 1)

		events = get_scheduler_events('daily_long')
		self.assertTrue('frappe.integrations.dropbox_integration.take_backups_daily' in events)

		dropbox_settings.db_set('enabled', 0)
