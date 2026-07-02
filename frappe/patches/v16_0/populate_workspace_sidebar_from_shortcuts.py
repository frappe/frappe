import click

import frappe


def execute():
	"""Give v15 workspaces a sidebar built from their shortcuts.

	v15 workspaces never had a `Workspace Sidebar`, so after the sidebar merge their
	`sidebar_items` table is empty and the desk UI breaks. For every workspace (public or
	private) that still lacks authored sidebar items, build a sidebar with a `Home` item
	pointing at the workspace itself followed by one `Link` item per `Workspace Shortcut`.

	Workspaces whose sidebar was already populated (e.g. from a migrated `Workspace Sidebar`)
	are left untouched, so this only fills the gap left by shortcut-only v15 workspaces.
	"""
	workspaces = frappe.get_all(
		"Workspace",
		fields=["name", "icon"],
		filters={"name": ("!=", "Welcome Workspace")},
	)

	for ws in workspaces:
		# Don't clobber an already-authored sidebar (e.g. from the Workspace Sidebar merge).
		if frappe.db.exists("Workspace Sidebar Item", {"parent": ws.name, "parenttype": "Workspace"}):
			continue

		try:
			workspace = frappe.get_doc("Workspace", ws.name)

			# `Home` links the workspace to itself so it always appears in its own sidebar.
			workspace.append(
				"sidebar_items",
				{
					"type": "Link",
					"label": "Home",
					"link_type": "Workspace",
					"link_to": ws.name,
					"icon": ws.icon,
				},
			)

			for shortcut in workspace.shortcuts:
				item = {
					"type": "Link",
					"label": shortcut.label,
					"icon": shortcut.icon,
				}
				if shortcut.type == "URL":
					item["link_type"] = "URL"
					item["url"] = shortcut.url
				else:
					item["link_type"] = shortcut.type
					item["link_to"] = shortcut.link_to
				workspace.append("sidebar_items", item)

			# These legacy workspaces often carry shortcuts pointing at deleted docs; ignore
			# link validation so a stale link doesn't block building the sidebar.
			workspace.flags.ignore_links = True
			workspace.save(ignore_permissions=True)
			frappe.db.commit()  # nosemgrep
			click.secho(f"Populated sidebar for Workspace '{ws.name}'", fg="green")
		except Exception as e:
			frappe.db.rollback()
			click.secho(f"Failed to populate sidebar for Workspace '{ws.name}'", fg="red")
			click.secho(str(e))
			frappe.log_error(title="Workspace sidebar population failed", reference_name=ws.name)
