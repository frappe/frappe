import frappe
from frappe.core.doctype.user_status_type.user_status_type import (
	seed_default_user_status_types,
)


def execute():
	"""Seed the six standard User Status Type rows on existing sites."""
	if not frappe.db.has_table("User Status Type"):
		# the doctype sync runs before patches; if the table isn't here yet
		# something else is wrong — bail rather than mask it
		return
	seed_default_user_status_types()
