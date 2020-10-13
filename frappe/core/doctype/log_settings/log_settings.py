# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.core.doctype.activity_log.activity_log import clear_activity_logs

class LogSettings(Document):
	def clear_logs(self):
		self.clear_error_logs()
		self.clear_activity_logs()

	def clear_error_logs(self):
		frappe.db.sql(""" DELETE FROM `tabError Log`
			WHERE `creation` < (NOW() - INTERVAL '{0}' DAY)
		""".format(self.error_log))

	def clear_activity_logs(self):
		clear_activity_logs(days=self.activity_log)

def run_log_clean_up():
	doc = frappe.get_doc("DocType", "Log Settings")
	doc.clear_logs()

def show_error_log_reminder():
	users_to_notify = get_users_to_notify()

	if frappe.db.count("Error Log", filters={'seen': 0}) > 0:
		for user in users_to_notify:
			frappe.publish_realtime('msgprint', {
				"message": _("You have unseen {0}").format('<a href="/desk#List/Error%20Log/List"> Error Log </a>'),
				"alert":1,
				"indicator" :"red"
			}, user=user)

def get_users_to_notify():
	from frappe.email import get_system_managers
	log_settings = frappe.get_doc('Log Settings')

	if log_settings.users_to_notify:
		return [u.user for u in log_settings.users_to_notify]
	else:
		return get_system_managers()

