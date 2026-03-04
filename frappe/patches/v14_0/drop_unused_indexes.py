"""
This patch just drops some known indexes which aren't being used anymore or never were used.
"""

import frappe
from frappe.database.utils import drop_index_if_exists

UNUSED_INDEXES = [
	("Comment", ["link_doctype", "link_name"]),
	("Activity Log", ["link_doctype", "link_name"]),
]


def execute():
	if frappe.db.db_type == "postgres":
		return

	db_tables = frappe.db.get_tables(cached=False)

	# All parent indexes
	parent_doctypes = frappe.get_all(
		"DocType",
		{"istable": 0, "is_virtual": 0, "issingle": 0},
		pluck="name",
	)
	db_tables = frappe.db.get_tables(cached=False)

	for doctype in parent_doctypes:
		table = f"tab{doctype}"
		if table not in db_tables:
			continue
		drop_index_if_exists(table, "parent")

	# Unused composite indexes
	for doctype, index_fields in UNUSED_INDEXES:
		table = f"tab{doctype}"
		index_name = frappe.db.get_index_name(index_fields)
		if table not in db_tables:
			continue
		drop_index_if_exists(table, index_name)
