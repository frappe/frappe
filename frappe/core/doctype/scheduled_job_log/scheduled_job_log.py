# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.query_builder import Interval
from frappe.query_builder.functions import Now


class ScheduledJobLog(Document):
	@staticmethod
	def clear_old_logs(days=90):
		table = frappe.qb.DocType("Scheduled Job Log")
		frappe.db.delete(table, filters=(table.modified < (Now() - Interval(days=days))))
