# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class WebhookRequestLog(Document):
	@staticmethod
	def clear_old_logs(days=30):
		from frappe.query_builder import Interval
		from frappe.query_builder.functions import Now

		table = frappe.qb.DocType("Webhook Request Log")
		frappe.db.delete(table, filters=(table.modified < (Now() - Interval(days=days))))
