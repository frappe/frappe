import click

import frappe
from frappe.desk.doctype.module_sidebar.module_sidebar import build_all


def execute():
	"""Carry every sidebar this site authored over into the layers that hold one now.

	Reads the **v16 archive** for a v16 site and a workspace's **shortcuts** for a v15 one,
	merges each module's sidebars into one, and stores the result as a site layer -- plus a
	user layer for every personal fork the archive holds, which is what that population's
	customizations actually are.

	Runs post_model_sync: `Custom Module Sidebar` is a new doctype, so its schema has to land
	first. It must also run after `backfill_workspace_module`, which is what gives a v15 site's
	workspaces a module to be grouped under; ahead of the backfill the shortcut route sees no
	sources at all and every module is left to a computed base.

	Non-destructive and re-runnable: every source row -- archive and workspace alike -- is left
	exactly as it was, and a module that already carries a layer is skipped. Undo is deleting
	the rows it created.
	"""
	if not frappe.db.exists("DocType", "Custom Module Sidebar"):
		return

	result = build_all()

	for plan in result["merged"]:
		if plan["secondaries"]:
			click.secho(
				f"Module '{plan['module']}': merged {plan['primary']} <- {', '.join(plan['secondaries'])}",
				fg="yellow",
			)

	for fork in result["personal"]:
		click.secho(
			f"Module '{fork['module']}': kept {fork['user']}'s own arrangement "
			f"from {', '.join(fork['sources'])}",
			fg="green",
		)

	if result["discarded"]:
		click.secho(
			f"Discarded {len(result['discarded'])} private-workspace container(s); "
			"those links are derived now.",
			fg="cyan",
		)

	click.secho(
		f"Converted {len(result['merged'])} module sidebar(s) and "
		f"{len(result['personal'])} personal fork(s); "
		f"{len(result['computed'])} module(s) left to a computed base.",
		fg="green",
	)
