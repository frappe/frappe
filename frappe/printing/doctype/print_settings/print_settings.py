# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.utils import cint

from frappe.model.document import Document

class PrintSettings(Document):
	def on_update(self):
		frappe.clear_cache()

	@frappe.whitelist()
	def get_printers(self,ip="localhost",port=631):
		printer_list = []
		try:
			import cups
		except ImportError:
			frappe.throw(_("You need to install pycups to use this feature!"))
			return
		try:
			cups.setServer(self.server_ip)
			cups.setPort(self.port)
			conn = cups.Connection()
			printers = conn.getPrinters()
			printer_list = printers.keys()
		except RuntimeError:
			frappe.throw(_("Failed to connect to server"))
		except frappe.ValidationError:
			frappe.throw(_("Failed to connect to server"))
		return printer_list

@frappe.whitelist()
def is_print_server_enabled():
	if not hasattr(frappe.local, 'enable_print_server'):
		frappe.local.enable_print_server = cint(frappe.db.get_single_value('Print Settings',
			'enable_print_server'))

	return frappe.local.enable_print_server
