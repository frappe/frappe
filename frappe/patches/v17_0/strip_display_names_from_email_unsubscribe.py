import frappe
from frappe.utils import extract_email_id


def execute():
	rows = frappe.get_all(
		"Email Unsubscribe", filters={"email": ("like", "%<%")}, fields=["name", "email"], as_list=True
	)
	frappe.db.bulk_update(
		"Email Unsubscribe",
		{name: {"email": extract_email_id(email)} for name, email in rows},
		update_modified=False,
	)
