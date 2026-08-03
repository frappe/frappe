import click

import frappe


def execute():
	"""Drop `Block Module` rows naming a module that no longer exists.

	`Block Module.module` becomes a Link to Module Def. A stale row -- a module from an app
	since uninstalled, or a typo from when this was free text -- would fail link validation
	on the user's next save, locking them out of editing their own profile.

	Runs pre_model_sync, before the Data -> Link column change lands.
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
