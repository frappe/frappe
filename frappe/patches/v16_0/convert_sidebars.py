import click

import frappe
from frappe.desk.doctype.sidebar.sidebar import build_sidebar
from frappe.patches.v16_0.sidebar_archive import (
	archive_exists,
	by_module,
	is_custom,
	is_module,
	site_rows,
	write_base,
	written_as_of,
)


def execute():
	"""Carry an app's v16 sidebars into the module's `Sidebar`, where the app has not shipped one.

	A site's own sidebars and a user's forks are converted by the patches after this one. The old
	rows are left untouched, so this is safe to re-run.
	"""
	if not archive_exists():
		return

	converted = []
	for module, sources in sorted(standard_sources().items()):
		# the app ships this module's sidebar, so it is the current arrangement
		if frappe.db.exists("Sidebar", {"module": module}):
			continue

		plan = build_sidebar(module, sources)
		write_base(module, plan, written_as_of(sources))
		converted.append(module)

		if plan["secondaries"]:
			click.secho(
				f"Module '{module}': merged {plan['primary']} <- {', '.join(plan['secondaries'])}",
				fg="yellow",
			)

	if converted:
		click.secho(f"Sidebars: {len(converted)} module(s) carried over.", fg="green")


def standard_sources() -> dict[str, list[frappe._dict]]:
	"""The app rows nothing shipped today stands for, grouped by module.

	A row is matched by title before module. An app that reorganised its modules ships the
	sidebar under its old title in a new module: hrms's v16 `Expenses` said `HR`, and is the
	`Expenses` sidebar of module `Expenses` now. Matched by module alone, every such row would be
	merged into a second, stale `HR` sidebar.
	"""
	rows = [
		row
		for row in site_rows()
		if not is_custom(row)
		and is_module(row.module)
		and not frappe.db.exists("Sidebar", {"name": row.name, "standard": 1})
	]
	return by_module(rows)
