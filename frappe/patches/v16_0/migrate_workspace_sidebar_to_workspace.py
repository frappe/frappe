import click

import frappe


def execute():
	"""Merge `Workspace Sidebar` into `Workspace`.

	The per-sidebar merge logic lives on the `Workspace Sidebar` controller
	(`migrate_to_workspace`) so it can be reused from the doctype form too.
	"""
	if not frappe.db.exists("DocType", "Workspace Sidebar"):
		return

	sidebar_names = frappe.get_all("Workspace Sidebar", pluck="name")

	for name in sidebar_names:
		# Sidebars named "My Workspaces" were created only to give v15 private
		# workspaces a sidebar; skip them as they have no standalone workspace.
		if "my workspaces" in name.lower():
			click.secho(f"Skipping Workspace Sidebar '{name}'", fg="yellow")
			continue
		try:
			frappe.get_doc("Workspace Sidebar", name).migrate_to_workspace()
		except frappe.NameError:
			click.secho(f"There is a doctype with the name {name}")
			click.secho("Change the Workspace Sidebar name to something else")
		except Exception as e:
			frappe.db.rollback()
			click.secho(f"Failed to migrate Workspace Sidebar '{name}' to Workspace", fg="red")
			click.secho(str(e))
			frappe.log_error(title="Workspace Sidebar migration failed", reference_name=name)

	frappe.db.commit()  # nosemgrep
