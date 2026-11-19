import frappe


def execute():
	if frappe.conf.allow_tests:
		return

	for email in ("admin@example.com", "guest@example.com"):
		unsubscribe = {"doctype": "Email Unsubscribe", "email": email, "global_unsubscribe": 1}
		if not frappe.db.exists(unsubscribe):
			frappe.get_doc(unsubscribe).insert(ignore_permissions=True)
