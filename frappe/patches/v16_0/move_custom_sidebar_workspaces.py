import click

import frappe
from frappe.patches.v16_0.sidebar_archive import archive_exists, converted_module_of, is_custom, site_rows


def execute():
	"""Move the workspace each custom sidebar opened on into the module the sidebar became.

	A desktop icon finds its sidebar through the module of the workspace it links to, and v16's
	icon for a custom sidebar links to a workspace of the same name. Left in the module v16 filed
	it under, the icon opens that module's sidebar instead of the site's own.

	Only a page the site made is moved. An app's workspace belongs where the app put it.
	"""
	if not archive_exists():
		return

	moved = False
	for row in site_rows():
		if not is_custom(row):
			continue

		module = converted_module_of(row.name)
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
