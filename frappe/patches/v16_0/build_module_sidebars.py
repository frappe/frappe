import click

import frappe
from frappe.desk.doctype.module_sidebar.module_sidebar import build_all


def execute():
	"""Carry each module's authored sidebars over into one `Module Sidebar`.

	Merges each module's authored `Workspace.sidebar_items` into one sidebar -- the largest
	workspace leads, the rest become collapsed sections. A module that authored none gets no
	row: its base is computed from its contents on read.

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
		f"Built {len(result['merged'])} Module Sidebar(s) from workspaces; "
		f"{len(result['computed'])} module(s) left to a computed base.",
		fg="green",
	)
