import frappe

def execute():
	web_pages = frappe.get_all('Web Page', ['name', 'description'])

	for web_page in web_pages:
		if web_page.description:
			doc = frappe.get_doc('Web Page', web_page.name)
			doc.append('meta_tags', {
				'key': 'description',
				'value': web_page.description
			})
			doc.save()
