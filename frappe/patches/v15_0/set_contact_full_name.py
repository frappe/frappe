import frappe
from frappe.contacts.doctype.contact.contact import get_full_name
from frappe.utils import update_progress_bar


def execute():
	"""Set full name for all contacts"""
	frappe.db.auto_commit_on_many_writes = 1

	contacts = frappe.get_all(
		"Contact",
		fields=["name", "first_name", "middle_name", "last_name", "company_name"],
		filters={"full_name": ("is", "not set")},
		as_list=True,
	)
	total = len(contacts)
	for idx, (name, first, middle, last, company) in enumerate(contacts):
		update_progress_bar("Setting full name for contacts", idx, total)
		try:
			frappe.db.set_value(
				"Contact",
				name,
				"full_name",
				get_full_name(first, middle, last, company),
				update_modified=False,
			)
		except frappe.db.DataError as e:
			if frappe.db.is_data_too_long(e):
				print("Full name is too long for DB column, skipping")
				continue
			raise e
