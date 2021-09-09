# Copyright (c) 2021, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _

class PrinterSettings(Document):
	@frappe.whitelist()
	def get_printers_list(self,ip="localhost",port=631):
		print("``````````````````````````````````")
		print(ip)
		print(port)
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
			for printer_id,printer in printers.items():
				printer_list.append({
					'value': printer_id,
					'label': printer['printer-make-and-model']
				})
			print(printer_list)
			print("``````````````````````````````````")
		except RuntimeError:
			frappe.throw(_("Failed to connect to server"))
		except frappe.ValidationError:
			frappe.throw(_("Failed to connect to server"))
		return printer_list

@frappe.whitelist()
def get_printer_setting(doctype):
	return frappe.db.get_value('Printer Settings', {'reference_doctype': doctype})