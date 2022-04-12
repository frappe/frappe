import click

import frappe


def execute():
	doctype = "Data Import Legacy"
	table = frappe.utils.get_table_name(doctype)

	# delete the doctype record to avoid broken links
	frappe.db.delete("DocType", {"name": doctype})

	# leaving table in database for manual cleanup
	click.secho(
		f"`{doctype}` has been deprecated. The DocType is deleted, but the data still"
		" exists on the database. If this data is worth recovering, you may export it"
		f" using\n\n\tbench --site {frappe.local.site} backup -i '{doctype}'\n\nAfter"
		" this, the table will continue to persist in the database, until you choose"
		" to remove it yourself. If you want to drop the table, you may run\n\n\tbench"
		f" --site {frappe.local.site} execute frappe.db.sql --args \"('DROP TABLE IF"
		f" EXISTS `{table}`', )\"\n",
		fg="yellow",
	)
