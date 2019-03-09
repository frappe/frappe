# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
    if frappe.db.table_exists('User Permission for Page and Report'):
        frappe.delete_doc("DocType", "User Permission for Page and Report")