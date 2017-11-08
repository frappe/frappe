import frappe

@frappe.whitelist()
def get_contact_list():
	docs = frappe.get_all('User', fields = [
		"first_name", "last_name", "last_active"
	])

	return docs