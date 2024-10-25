import frappe

from ...user.user import desk_properties


def execute() -> None:
	for role in frappe.get_all("Role", ["name", "desk_access"]):
		role_doc = frappe.get_doc("Role", role.name)
		for key in desk_properties:
			role_doc.set(key, role_doc.desk_access)
		role_doc.save()
