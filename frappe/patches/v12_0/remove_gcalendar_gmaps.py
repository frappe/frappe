import frappe

def execute():
	'''
		Remove GCalendar and GCalendar Settings
		Remove Google Maps Settings as its been merged with Delivery Trips
	'''
	frappe.delete_doc_if_exists('DocType', 'GCalendar Account')
	frappe.delete_doc_if_exists('DocType', 'GCalendar Settings')
	frappe.delete_doc_if_exists('DocType', 'Google Maps Settings')
