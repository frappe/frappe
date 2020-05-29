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
		if (self.is_standard and not frappe.conf.developer_mode and not disable_saving_as_standard()):
			frappe.throw(_("You need to be in developer mode to edit this document"))

	def on_update(self):
		if disable_saving_as_standard():
			return

		if frappe.conf.developer_mode and self.is_standard:
			export_to_files(record_list=[['Desk Page', self.name]], record_module=self.module)

	@staticmethod
	def get_module_page_map():
		filters = {
			'extends_another_page': 0,
			'for_user': '',
		}

		pages = frappe.get_all("Desk Page", fields=["name", "module"], filters=filters, as_list=1)

		return { page[1]: page[0]  for page in pages }

def disable_saving_as_standard():
	return frappe.flags.in_install or \
			frappe.flags.in_patch or \
			frappe.flags.in_test or \
			frappe.flags.in_fixtures or \
			frappe.flags.in_migrate