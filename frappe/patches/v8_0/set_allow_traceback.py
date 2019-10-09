from __future__ import unicode_literals
import frappe

def execute():
    frappe.reload_doc('core', 'doctype', 'system_settings')
    frappe.db.sql("update `tabSystem Settings` set allow_error_traceback=1")
