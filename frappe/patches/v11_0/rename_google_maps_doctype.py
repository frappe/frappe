from __future__ import unicode_literals
import frappe
from frappe.model.rename_doc import rename_doc

def execute():
	if frappe.db.exists("DocType","Google Maps") and not frappe.db.exists("DocType","Google Maps Settings"):
		rename_doc('DocType', 'Google Maps', 'Google Maps Settings')
