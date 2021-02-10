import frappe

def execute():
	providers = frappe.get_all("Social Login Key")

	for provider in providers:
		doc = frappe.get_doc("Social Login Key", provider)
		doc.set_icon()
		doc.save()