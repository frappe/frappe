import click

import frappe
from frappe.patches.v16_0.sidebar_archive import archive_exists, custom_module_of, is_custom, site_rows


def execute():
	"""Move the workspace each custom sidebar opened on into the sidebar's new custom module.

	A desktop icon links to a workspace, and opens the sidebar of that workspace's module. If the
	workspace stayed in its old module, the icon would open the app's sidebar instead of the
	site's own.

	Only workspaces the site made are moved. An app's workspace stays where the app put it.
	"""
	if not archive_exists():
		return

	moved = False
	for row in site_rows():
		if not is_custom(row):
			continue

		module = custom_module_of(row.name)
		workspace = frappe.db.get_value(
			"Workspace",
			{"name": row.name, "standard": 0, "for_user": ["is", "not set"]},
			["name", "module"],
			as_dict=True,
		)
		if not module or not workspace or workspace.module == module:
			continue

		frappe.db.set_value("Workspace", workspace.name, "module", module, update_modified=False)
		moved = True
		click.secho(
			f"Workspace '{workspace.name}': moved from '{workspace.module}' to '{module}'", fg="green"
		)

	# a workspace's module decides which sidebar its desktop icon opens, and both are cached
	if moved:
		frappe.clear_cache()
