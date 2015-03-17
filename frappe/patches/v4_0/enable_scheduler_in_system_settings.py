# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils.scheduler import disable_scheduler, enable_scheduler
from frappe.utils import cint

def execute():
	frappe.reload_doc("core", "doctype", "system_settings")
	if cint(frappe.db.get_global("disable_scheduler")):
		disable_scheduler()
	else:
		enable_scheduler()
