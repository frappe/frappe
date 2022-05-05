import frappe


def execute():
	categories = frappe.get_list("Blog Category")
	for category in categories:
		doc = frappe.get_doc("Blog Category", category["name"])
		doc.set_route()
		doc.save()
