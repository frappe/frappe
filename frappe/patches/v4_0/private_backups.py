# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.installer import make_site_dirs

def execute():
	make_site_dirs()
	if frappe.local.conf.backup_path and frappe.local.conf.backup_path.startswith("public"):
		raise Exception("Backups path in conf set to public directory")
