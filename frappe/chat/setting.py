# imports - module imports
import frappe

@frappe.whitelist()
def get_user_status(user):
	doc = frappe.get_doc('User', user)
	
	return doc.chat_status

@frappe.whitelist()
def set_user_status(user, status):
	doc = frappe.get_doc('User', user)
	doc.chat_status = status
	doc.save()