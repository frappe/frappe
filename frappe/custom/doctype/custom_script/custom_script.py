# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals
import frappe

from frappe.model.document import Document

class CustomScript(Document):
	def autoname(self):
		self.name = self.dt + "-Client"

	def on_update(self):
		frappe.clear_cache(doctype=self.dt)

	def on_trash(self):
		frappe.clear_cache(doctype=self.dt)

