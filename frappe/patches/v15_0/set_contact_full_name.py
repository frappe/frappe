import frappe
from frappe.contacts.doctype.contact.contact import get_full_name


def execute():
	"""Set full name for all contacts"""
	for name, first, middle, last, company in frappe.get_all(
		"Contact",
		fields=["name", "first_name", "middle_name", "last_name", "company_name"],
		as_list=True,
	):
		frappe.db.set_value("Contact", name, "full_name", get_full_name(first, middle, last, company))
