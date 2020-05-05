import frappe

def execute():
	frappe.reload_doctype('Website Theme')
	for theme in frappe.get_all('Website Theme'):
		doc = frappe.get_doc('Website Theme', theme.name)
		if not doc.get('custom_scss') and doc.theme_scss:
			# move old theme to new theme
			doc.custom_scss = doc.theme_scss
			doc.save()
