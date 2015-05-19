# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("core", "doctype", "report")
	frappe.db.sql("""update `tabReport` r set r.module=(select d.module from `tabDocType` d
		where d.name=r.ref_doctype) where ifnull(r.module, '')=''""")