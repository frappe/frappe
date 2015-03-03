# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("core", "doctype", "outgoing_email_settings")
	if (frappe.db.get_value("Outgoing Email Settings", "Outgoing Email Settings", "mail_server") or "").strip():
		frappe.db.set_value("Outgoing Email Settings", "Outgoing Email Settings", "enabled", 1)
