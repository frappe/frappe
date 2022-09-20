# Copyright (c) 2015, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.query_builder import Interval
from frappe.query_builder.functions import Now


class ErrorLog(Document):
	def onload(self):
		if not self.seen and not frappe.flags.read_only:
			self.db_set("seen", 1, update_modified=0)
			frappe.db.commit()

	@staticmethod
	def clear_old_logs(days=30):
		table = frappe.qb.DocType("Error Log")
		frappe.db.delete(table, filters=(table.modified < (Now() - Interval(days=days))))


@frappe.whitelist()
def clear_error_logs():
	"""Flush all Error Logs"""
	frappe.only_for("System Manager")
	frappe.db.truncate("Error Log")
