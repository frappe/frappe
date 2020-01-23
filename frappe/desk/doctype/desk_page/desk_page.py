# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
# import frappe
from frappe.model.document import Document

class DeskPage(Document):
	def on_update(self):
		export_to_files(record_list=[['Desk Page', self.name]], record_module="Desk")
