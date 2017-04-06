# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors

from __future__ import unicode_literals
import frappe

def execute():
	frappe.db.set_value("DocType", "Contact", "module", "Contacts")
	frappe.db.set_value("DocType", "Address", "module", "Contacts")
	frappe.db.set_value("DocType", "Address Template", "module", "Contacts")