# -*- coding: utf-8 -*-
# Copyright (c) 2021, Frappe and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import unittest
import frappe
from frappe.utils.backups import BackupGenerator


class TestBackups(unittest.TestCase):
	def test_error_on_failed_backup(self):
		"""bench backup command should fail in case of an error"""
		odb = BackupGenerator(
			frappe.conf.db_name,
			frappe.conf.db_name,
			frappe.conf.db_password,
			db_type=frappe.conf.db_type,
			db_host="NON_EXISTENT_HOST",
		)
		self.assertRaises(Exception, odb.get_backup, force=True)
