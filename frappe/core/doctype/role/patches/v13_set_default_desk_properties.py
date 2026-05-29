import frappe
from frappe.doctypes import Role

from ...user.user import desk_properties


def execute():
	for role in frappe.get_all("Role", ["name", "desk_access"]):
		role_doc = Role.docs.get(role.name)
		for key in desk_properties:
			role_doc.set(key, role_doc.desk_access)
		role_doc.save()
