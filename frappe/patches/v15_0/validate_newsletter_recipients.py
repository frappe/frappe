import frappe
from frappe.utils import validate_email_address


def execute():
	for name, email in frappe.get_all("Email Group Member", fields=["name", "email"], as_list=True):
		if not validate_email_address(email, throw=False):
			frappe.db.set_value("Email Group Member", name, "unsubscribed", 1)
			frappe.db.commit()
