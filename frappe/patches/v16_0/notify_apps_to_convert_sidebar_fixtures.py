import click

import frappe


def execute():
	"""Tell app authors once that `<app>/workspace_sidebar/*.json` is no longer imported.

	Those modules fall back to a sidebar generated from their contents, so nothing breaks, but
	erpnext and hrms would lose their curated navigation on upgrade. Only apps that still hold
	fixtures are named.
	"""
	from frappe.desk.doctype.sidebar.convert_fixtures import apps_with_old_fixtures

	counts = apps_with_old_fixtures()
	if not counts:
		return

	total = sum(counts.values())
	click.secho(
		f"\n{total} sidebar fixture(s) in {len(counts)} app(s) are in a format that is no longer imported:",
		fg="yellow",
		bold=True,
	)
	for app, count in sorted(counts.items()):
		click.secho(f"  {app:24} {count} file(s) in {app}/workspace_sidebar/", fg="yellow")

	click.secho(
		"\nThose modules fall back to a sidebar generated from their contents until the app "
		"re-exports. To convert:",
		fg="yellow",
	)
	click.secho(f"  bench --site {frappe.local.site} convert-sidebar-fixtures --app <app>\n", bold=True)
