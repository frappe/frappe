import frappe
import frappe.share


def execute():
	for user in frappe.STANDARD_USERS:
		frappe.share.remove("User", user, user)
