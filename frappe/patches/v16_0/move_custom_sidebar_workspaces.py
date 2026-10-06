import click

import frappe
from frappe.patches.v16_0.sidebar_archive import archive_exists, custom_module_of, is_custom, site_rows


def execute():
	"""Move the workspace each custom sidebar opened on into that sidebar's module, so its desktop
	icon opens the site's sidebar and not the app's."""
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
