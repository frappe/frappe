import frappe

from ..role import desk_properties


def execute():
	frappe.reload_doctype("user")
	frappe.reload_doctype("role")
	for role in frappe.get_all("Role", ["name", "desk_access"]):
		role_doc = frappe.get_doc("Role", role.name)
		for key in desk_properties:
			role_doc.set(key, role_doc.desk_access)
		role_doc.save()
