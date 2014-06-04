# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils.scheduler import disable_scheduler, enable_scheduler

def execute():
	frappe.reload_doc("core", "doctype", "system_settings")
	if frappe.db.get_global("disable_scheduler"):
		disable_scheduler()
	else:
		enable_scheduler()
