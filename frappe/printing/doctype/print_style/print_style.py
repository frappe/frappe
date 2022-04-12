# -*- coding: utf-8 -*-
# Copyright (c) 2017, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class PrintStyle(Document):
	def validate(self):
		if (
			self.standard == 1
			and not frappe.local.conf.get("developer_mode")
			and not (frappe.flags.in_import or frappe.flags.in_test)
		):

			frappe.throw(frappe._("Standard Print Style cannot be changed. Please duplicate to edit."))

	def on_update(self):
		self.export_doc()

	def export_doc(self):
		# export
		from frappe.modules.utils import export_module_json

		export_module_json(self, self.standard == 1, "Printing")
