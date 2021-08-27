# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

import frappe

def execute():
        frappe.delete_doc_if_exists("DocType", "User Permission for Page and Report")