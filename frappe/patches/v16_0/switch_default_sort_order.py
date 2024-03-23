import click

import frappe
from frappe.patches.v14_0.drop_unused_indexes import drop_index_if_exists


def execute():
	if frappe.db.db_type == "postgres":
		return

	db_tables = frappe.db.get_tables(cached=False)

	doctypes = frappe.get_all(
		"DocType",
		{"is_virtual": 0, "istable": 0},
		pluck="name",
	)

	for doctype in doctypes:
		table = f"tab{doctype}"
		if table not in db_tables:
			continue
		frappe.db.add_index(doctype, ["creation"], index_name="creation")
		click.echo(f"✓ created creation index from {table}")
		drop_index_if_exists(table, "modified")
