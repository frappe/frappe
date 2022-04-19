import frappe


def execute():

	frappe.db.sql("UPDATE `tabTag Link` SET parenttype=document_type")
	frappe.db.sql("UPDATE `tabTag Link` SET parent=document_name")
