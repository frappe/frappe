# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.modules.export_file import export_to_files


class DashboardChartSource(Document):
	def validate(self):
		if frappe.session.user != "Administrator":
			frappe.throw(_("Only Administrator is allowed to create Dashboard Chart Sources"))

	def on_update(self):
		export_to_files(record_list=[[self.doctype, self.name]], record_module=self.module, create_init=True)
