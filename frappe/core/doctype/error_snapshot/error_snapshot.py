# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.query_builder import Interval
from frappe.query_builder.functions import Now


class ErrorSnapshot(Document):
	no_feed_on_delete = True

	def onload(self):
		if not self.parent_error_snapshot:
			self.db_set("seen", 1, update_modified=False)

			for relapsed in frappe.get_all("Error Snapshot", filters={"parent_error_snapshot": self.name}):
				frappe.db.set_value("Error Snapshot", relapsed.name, "seen", 1, update_modified=False)

			frappe.local.flags.commit = True

	def validate(self):
		parent = frappe.get_all(
			"Error Snapshot",
			filters={"evalue": self.evalue, "parent_error_snapshot": ""},
			fields=["name", "relapses", "seen"],
			limit_page_length=1,
		)

		if parent:
			parent = parent[0]
			self.update({"parent_error_snapshot": parent["name"]})
			frappe.db.set_value("Error Snapshot", parent["name"], "relapses", parent["relapses"] + 1)
			if parent["seen"]:
				frappe.db.set_value("Error Snapshot", parent["name"], "seen", 0)

	@staticmethod
	def clear_old_logs(days=30):
		table = frappe.qb.DocType("Error Snapshot")
		frappe.db.delete(table, filters=(table.modified < (Now() - Interval(days=days))))
