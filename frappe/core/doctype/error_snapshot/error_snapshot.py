# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class ErrorSnapshot(Document):
	def onload(self):
		if not self.parent_error_snapshot:
			self.seen = True

			frappe.db.set_value("Error Snapshot", self.name, "seen", True)

			for relapsed in frappe.db.get_list("Traceback", filters=[[
				"Error Snapshot", "parent_error_snapshot", "=", self.name]]):
				frappe.db.set_value("error_snapshot", relapsed["name"], "seen", True)

			frappe.db.commit()

	def validate(self):
		parent = frappe.get_list('Error Snapshot', filters=[
			['Error Snapshot', 'evalue', '=', self.evalue],
			['Error Snapshot', 'parent_error_snapshot', '=', None]], fields=["name", "relapses", "seen"])

		if parent:
			parent = parent[0]
			self.update({"parent_error_snapshot": parent['name']})
			frappe.db.set_value('Error Snapshot', parent['name'], 'relapses', parent["relapses"] + 1)
			if parent["seen"]:
				frappe.db.set_value("Error Snapshot", parent["name"], "seen", False)
