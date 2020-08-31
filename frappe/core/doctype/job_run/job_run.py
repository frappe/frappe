# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import error_log
from frappe.model.document import Document

class JobRun(Document):
	def start(self):
		self.status = 'Executing'
		self.started_at = frappe.utils.now_datetime()
		self.db_update()
		return self.started_at

	def finish(self, status, error_log=None):
		self.finished_at = frappe.utils.now_datetime()
		self.total_time = (self.finished_at - self.started_at).seconds
		self.sql_time = frappe.local.sql_time
		self.python_time = (self.total_time - self.sql_time) if self.total_time else 0
		self.status = status
		self.error_log = error_log
		self.modified = self.finished_at
		self.db_update()
		self.run_method('on_status_change')