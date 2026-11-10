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
	"""Build a `Sidebar` from an app's v16 sidebar, but only when the app no longer ships it.

	Usually the app ships its sidebars as files, and `bench migrate` has already installed them
	before this runs, so there is nothing to do. This covers an app that dropped a sidebar, or has
	not yet converted its old sidebar files.

	Sidebars the site made and users' personal copies are handled by the patches after this one.
	The old rows are not changed, so this is safe to run again.
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
	"""The app's v16 sidebars that the app no longer ships, grouped by module.

	A row is skipped when the app ships a sidebar with the same title, in any module. Checking
	the module alone is not enough when an app has moved a sidebar: if `Books` was under
	`Library` in v16 and now ships under `Catalog`, the old row still says `Library`. `Library`
	has no sidebar now, so the row would be built into a second, outdated `Library` sidebar.
	"""
	rows = [
		row
		for row in site_rows()
		if not is_custom(row)
		and is_module(row.module)
		and not frappe.db.exists("Sidebar", {"name": row.name, "standard": 1})
	]
	return by_module(rows)
