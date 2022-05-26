# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.model.document import Document


class LogSettings(Document):
	def clear_logs(self):
		self.clear_email_queue()
		self.clear_error_logs()
		self.clear_activity_logs()

	def clear_error_logs(self):
		frappe.db.sql(
			""" DELETE FROM `tabError Log`
			WHERE `creation` < (NOW() - INTERVAL '{0}' DAY)
		""".format(
				self.clear_error_log_after
			)
		)

	def clear_activity_logs(self):
		from frappe.core.doctype.activity_log.activity_log import clear_activity_logs

		clear_activity_logs(days=self.clear_activity_log_after)

	def clear_email_queue(self):
		from frappe.email.queue import clear_outbox

		clear_outbox(days=self.clear_email_queue_after)


def run_log_clean_up():
	doc = frappe.get_doc("Log Settings")
	doc.clear_logs()


@frappe.whitelist()
def has_unseen_error_log(user):
	def _get_response(show_alert=True):
		return {
			"show_alert": True,
			"message": _("You have unseen {0}").format(
				'<a href="/app/List/Error%20Log/List"> Error Logs </a>'
			),
		}

	if frappe.db.sql_list("select name from `tabError Log` where seen = 0 limit 1"):
		log_settings = frappe.get_cached_doc("Log Settings")

		if log_settings.users_to_notify:
			if user in [u.user for u in log_settings.users_to_notify]:
				return _get_response()
			else:
				return _get_response(show_alert=False)
		else:
			return _get_response()
