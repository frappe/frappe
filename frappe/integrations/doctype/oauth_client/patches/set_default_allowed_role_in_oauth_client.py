import frappe
from frappe.doctypes import OAuthClient


def execute():
	"""Set default allowed role in OAuth Client"""
	for client in frappe.get_all("OAuth Client", pluck="name"):
		doc = OAuthClient.docs.get(client)
		if doc.allowed_roles:
			continue
		row = doc.append("allowed_roles", {"role": "All"})  # Current default
		row.db_insert()
