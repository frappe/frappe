# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class LogSettings(Document):
	def clear_logs(self):
		self.clear_error_logs()
		self.clear_activity_logs()
		self.clear_email_queue()

	def clear_error_logs(self):
		frappe.db.sql(""" DELETE FROM `tabError Log`
			WHERE `creation` < (NOW() - INTERVAL '{0}' DAY)
		""".format(self.clear_error_log_after))

	def clear_activity_logs(self):
		from frappe.core.doctype.activity_log.activity_log import clear_activity_logs
		clear_activity_logs(days=self.clear_activity_log_after)

	def clear_email_queue(self):
		from frappe.email.queue import clear_outbox
		clear_outbox(days=self.clear_email_queue_after)

def run_log_clean_up():
	doc = frappe.get_doc("Log Settings")
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

