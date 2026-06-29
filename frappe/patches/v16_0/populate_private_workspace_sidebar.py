import click

import frappe


def execute():
	"""Give always-private workspaces a sidebar pointing at themselves.

	Private workspaces from v15 never had a `Workspace Sidebar`, so after the
	sidebar merge their `sidebar_items` table is empty and the desk UI breaks.
	Populate each such workspace with a single sidebar item linking to itself.
	"""

	private_workspaces = frappe.get_all(
		"Workspace",
		filters={"public": 0},
		fields=["name", "label", "title", "icon"],
	)

	for ws in private_workspaces:
		# Skip workspaces that already have a sidebar so re-runs don't add duplicates.
		if frappe.db.exists("Workspace Sidebar Item", {"parent": ws.name, "parenttype": "Workspace"}):
			continue

		try:
			workspace = frappe.get_doc("Workspace", ws.name)
			workspace.append(
				"sidebar_items",
				{
					"type": "Link",
					"label": ws.label or ws.title or ws.name,
					"link_type": "Workspace",
					"link_to": ws.name,
					"icon": ws.icon,
				},
			)
			# These legacy workspaces often carry shortcuts/links pointing at deleted
			# docs; ignore link validation so a stale link doesn't block the sidebar item.
			workspace.flags.ignore_links = True
			workspace.save(ignore_permissions=True)
			click.secho(f"Populated sidebar for private Workspace '{ws.name}'", fg="green")
		except Exception as e:
			frappe.db.rollback()
			click.secho(f"Failed to populate sidebar for Workspace '{ws.name}'", fg="red")
			click.secho(str(e))
			frappe.log_error(title="Private workspace sidebar population failed", reference_name=ws.name)

	frappe.db.commit()  # nosemgrep
