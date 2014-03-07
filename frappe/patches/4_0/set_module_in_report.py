# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.db.sql("""update `tabReport` r set r.module=(select d.module from `tabDocType` d
		where d.name=r.ref_doctype) where ifnull(r.module, '')=''""")