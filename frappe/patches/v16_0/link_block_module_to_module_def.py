import click

import frappe


def execute():
	"""Delete Block Module rows naming a module that no longer exists.

	`Block Module.module` becomes a Link to Module Def, and a stale row would stop the user from
	saving their own profile. Runs before the column change lands.
	"""
	if not frappe.db.exists("DocType", "Block Module"):
		return

	modules = set(frappe.get_all("Module Def", pluck="name"))
	stale = [
		row
		for row in frappe.get_all("Block Module", fields=["name", "module", "parent"])
		if row.module not in modules
	]

	if not stale:
		return

	for row in stale:
		click.secho(
			f"Dropping Block Module row for unknown module '{row.module}' (user {row.parent})",
			fg="yellow",
		)

	frappe.db.delete("Block Module", {"name": ["in", [row.name for row in stale]]})
