# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from erpnext.setup.install import default_system_signature

def execute():
	system_signature = frappe.db.get_default('mail_footer') or ''
	if not system_signature:
		system_signature = default_system_signature

	frappe.db.set_value("Outgoing Email Settings", "Outgoing Email Settings", "system_signature", system_signature)
