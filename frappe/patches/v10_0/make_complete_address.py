import frappe

def execute():
	# Fetch complete address in newly added field 'complete_address'
	existing_addresses = frappe.get_all("Address")
	for address in existing_addresses:
		address_doc = frappe.get_doc("Address",address)
		address_doc.make_complete_address()
		address_doc.save()