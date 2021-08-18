# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ErrorSnapshot(Document):
	no_feed_on_delete = True

	def onload(self):
		if not self.parent_error_snapshot:
			self.db_set('seen', True, update_modified=False)

			for relapsed in frappe.get_all("Error Snapshot", filters={"parent_error_snapshot": self.name}):
				frappe.db.set_value("Error Snapshot", relapsed.name, "seen", True, update_modified=False)

			frappe.local.flags.commit = True

	def validate(self):
		parent = frappe.get_all("Error Snapshot",
			filters={"evalue": self.evalue, "parent_error_snapshot": ""},
			fields=["name", "relapses", "seen"], limit_page_length=1)

		if parent:
			parent = parent[0]
			self.update({"parent_error_snapshot": parent['name']})
			frappe.db.set_value('Error Snapshot', parent['name'], 'relapses', parent["relapses"] + 1)
			if parent["seen"]:
				frappe.db.set_value("Error Snapshot", parent["name"], "seen", False)
