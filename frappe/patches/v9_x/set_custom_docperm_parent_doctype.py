import frappe

def execute():
    frappe.reload_doc('core', 'doctype', 'custom_docperm')
    frappe.db.sql("update `tabCustom DocPerm` set parent_doctype = parent")