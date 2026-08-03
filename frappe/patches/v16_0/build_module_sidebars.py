import click

import frappe
from frappe.desk.doctype.module_sidebar.module_sidebar import build_all


def execute():
	"""Give every Module Def a `Module Sidebar`, 1:1.

	Merges each module's authored `Workspace.sidebar_items` into one sidebar -- the largest
	workspace leads, the rest become collapsed sections -- then generates a sidebar for every
	module that ships none.

	Runs post_model_sync: `Module Sidebar` is a new doctype, so its schema has to land first.
	It must also run after `migrate_workspace_sidebar_to_workspace`, which is what populates
	`Workspace.sidebar_items` on a v15 site -- that is this patch's only input.

	Non-destructive and re-runnable: it reads `Workspace.sidebar_items` and writes only new
	`Module Sidebar` rows, never touching the source or the legacy `Workspace Sidebar` table.
	Undo is deleting the rows it created.
	"""
	if not frappe.db.exists("DocType", "Module Sidebar"):
		return

	result = build_all()

	for plan in result["merged"]:
		if plan["secondaries"]:
			click.secho(
				f"Module Sidebar '{plan['module']}': merged {plan['primary']} "
				f"<- {', '.join(plan['secondaries'])}",
				fg="yellow",
			)

	click.secho(
		f"Built {len(result['merged'])} Module Sidebar(s) from workspaces, "
		f"generated {len(result['generated'])}.",
		fg="green",
	)
