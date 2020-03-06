# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.modules.export_file import export_to_files
from frappe.model.document import Document

class DeskPage(Document):
	def validate(self):
		if (not (frappe.flags.in_install or frappe.flags.in_patch or frappe.flags.in_test or frappe.flags.in_fixtures)
			and not frappe.conf.developer_mode):
			frappe.throw(_("You need to be in developer mode to edit this document"))

	def on_update(self):
		export_to_files(record_list=[['Desk Page', self.name]], record_module=self.module)
