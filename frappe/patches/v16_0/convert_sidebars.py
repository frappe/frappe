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
	"""A sidebar is only built from old rows when the app no longer ships one at all."""
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
	"""The app rows to convert, by module. A row is skipped when the app ships a sidebar with
	the same name, in any module, so a sidebar the app moved is not built twice."""
	rows = [
		row
		for row in site_rows()
		if not is_custom(row)
		and is_module(row.module)
		and not frappe.db.exists("Sidebar", {"name": row.name, "standard": 1})
	]
	return by_module(rows)
