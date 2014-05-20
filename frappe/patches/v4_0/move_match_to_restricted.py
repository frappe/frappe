# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.reload_doc("core", "doctype", "docperm")
	frappe.db.sql("""update `tabDocPerm` set restricted=1 where `match`='owner'""")