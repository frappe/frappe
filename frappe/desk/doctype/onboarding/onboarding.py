# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
from frappe.modules.export_file import export_to_files

class Onboarding(Document):
	def on_update(self):
		if frappe.conf.developer_mode:
			export_to_files(record_list=[['Onboarding', self.name]], record_module=self.module)

			for step in self.steps:
				export_to_files(record_list=[['Onboarding Step', step.step]], record_module=self.module)