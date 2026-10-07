import click

import frappe
from frappe.desk.doctype.dock.dock import drop_dock_caches
from frappe.desk.doctype.sidebar.sidebar import build_sidebar
from frappe.patches.v16_0.sidebar_archive import (
	archive_exists,
	generated_from_app_workspace,
	is_module,
	modules_converted_from,
	site_rows,
	write_base,
	written_as_of,
)


def execute():
	"""Remove the custom modules an earlier `convert_custom_sidebars` made from sidebars v16 had
	generated from app workspaces.

	That patch took such a row for one the site made, and gave it a module of its own, `Raven
	(Custom)`, beside the app's `Raven`. The row is the app's content, so the app's module is
	where it belongs: it is carried there when that module has no sidebar yet, and the extra
	module goes, with its sidebar, dock entries and the users it was blocked for.
	"""
	if not archive_exists():
		return

	removed = []
	for row in site_rows():
		if row.standard or row.app or not generated_from_app_workspace(row):
			continue

		for module in modules_converted_from(row.name):
			if module == row.module or not frappe.db.get_value("Module Def", module, "custom"):
				continue
			if is_module(row.module) and not frappe.db.exists("Sidebar", {"module": row.module}):
				write_base(row.module, build_sidebar(row.module, [row]), written_as_of([row]))
			remove_module(module)
			removed.append(module)
			click.secho(f"Module '{module}': removed, its sidebar is '{row.module}'s", fg="yellow")

	if removed:
		frappe.clear_cache()


def remove_module(module: str) -> None:
	sidebars = frappe.get_all("Sidebar", filters={"module": module}, pluck="name")
	for entry in frappe.get_all(
		"Dock Item",
		filters={"link_type": "Sidebar", "link_to": ["in", sidebars]},
		fields=["name", "parent"],
	):
		frappe.db.delete("Dock Item", {"name": entry.name})
		drop_dock_caches(frappe.db.get_value("Dock", entry.parent, "user"))

	frappe.db.delete("Block Module", {"parenttype": "User", "module": module})
	# `force`: nothing may hold the module back; the rows that pointed at it are gone above
	frappe.delete_doc("Module Def", module, force=True, ignore_permissions=True)
