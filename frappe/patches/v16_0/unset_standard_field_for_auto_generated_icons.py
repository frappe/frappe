import frappe
from frappe.model.sync import check_if_record_exists


def execute():
	for icon in frappe.get_all("Desktop Icon"):
		icon_doc = frappe.get_doc("Desktop Icon", icon.name)
		try:
			if (icon_doc.standard and icon_doc.app) and not check_if_record_exists(
				"app",
				frappe.get_app_path(icon_doc.app),
				"Desktop Icon",
				icon_doc.name,
			):
				icon_doc.standard = 0
				icon_doc.save()
		except Exception as e:
			print("Error in unsetting standard field", e)
