import frappe


def execute():
	frappe.reload_doc("website", "doctype", "website_theme_ignore_app")
	frappe.reload_doc("website", "doctype", "color")
	frappe.reload_doc("website", "doctype", "website_theme")
	frappe.reload_doc("website", "doctype", "website_settings")

	for theme in frappe.get_all("Website Theme"):
		doc = frappe.get_doc("Website Theme", theme.name)
		if not doc.get("custom_scss") and doc.theme_scss:
			# move old theme to new theme
			doc.custom_scss = doc.theme_scss

			if doc.background_color:
				setup_color_record(doc.background_color)

			doc.save()


def setup_color_record(color):
	frappe.get_doc(
		{
			"doctype": "Color",
			"__newname": color,
			"color": color,
		}
	).save()
