import click

import frappe


def execute():
	"""Tell an app author, once, that their sidebar fixtures need converting.

	App-shipped `<app>/workspace_sidebar/*.json` stops being imported with this release. A
	module whose app has not re-exported degrades to a base computed from its own contents
	rather than to nothing, so nothing breaks -- but for erpnext and hrms that means their
	whole curated navigation reverting on upgrade, and an author who finds that out from a bug
	report has been failed by us rather than by the decision.

	A patch, not a migrate-time console line: this is a one-time fact, and a line printed on
	every migrate for the rest of the release is a nag. It runs at the upgrade boundary, which
	is where a migration notice belongs, and names the **installed apps that actually still
	hold a non-empty folder** -- an author whose app is already converted is told nothing at
	all. The docs are the net for anyone who installs a stale app later.
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
