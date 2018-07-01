# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
import cups

from frappe.model.document import Document

class PrintSettings(Document):
	def on_update(self):
		frappe.clear_cache()

	@frappe.whitelist()
	def get_printers(self,ip="localhost",port=631):
		printer_list = []
		try:
			cups.setServer(self.server_ip)
			cups.setPort(self.port)
			conn = cups.Connection()
			printers = conn.getPrinters()
			printer_list = printers.keys()
		except RuntimeError:
			frappe.throw(_("Failed to connect to server"))
		except ValidationError:
			frappe.throw(_("Failed to connect to server"))			
		return printer_list
