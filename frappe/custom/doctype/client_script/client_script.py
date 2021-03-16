# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals
import frappe

from frappe import _
from frappe.model.document import Document


class ClientScript(Document):
	def autoname(self):
		self.name = f"{self.dt}-{self.apply_to_view}"

	def validate(self):
		if not self.is_new():
			return

		exists = frappe.db.exists(
			"Client Script", {"dt": self.dt, "apply_to_view": self.apply_to_view}
		)
		if exists:
			frappe.throw(
				_("Client Script for {0} {1} already exists").format(frappe.bold(self.dt), self.apply_to_view),
				frappe.DuplicateEntryError,
			)

	def on_update(self):
		frappe.clear_cache(doctype=self.dt)

	def on_trash(self):
		frappe.clear_cache(doctype=self.dt)
