import click

import frappe


def execute():
	"""Carry each user's dock curation from `User.workspaces` to `User.dock_modules`.

	The dock now lists modules, so a curation stored as workspace names has to be mapped
	through `Workspace.module`. Several curated workspaces can share a module -- that is the
	whole point of the merge -- so the result is deduped, keeping first-seen order.

	Runs after `backfill_workspace_module`: ahead of it, a v15 site's workspaces have no
	module at all, so every curated row would map to nothing and each user's whole
	arrangement would be dropped. What can still fail to map afterwards is a curated
	workspace that no longer exists, which is named rather than passed over in silence --
	a dock a user arranged is not something to lose without saying so.
	"""
	if not frappe.db.exists("DocType", "Dock Module"):
		return

	rows = frappe.get_all(
		"User Workspaces",
		filters={"parenttype": "User"},
		fields=["parent", "workspace", "idx"],
		order_by="parent asc, idx asc",
	)
	if not rows:
		return

	modules = dict(frappe.get_all("Workspace", fields=["name", "module"], as_list=True, limit_page_length=0))

	# A user who already holds dock rows has been through this, so their curation is left
	# alone -- and left out entirely, rather than filtered later: everything reported below
	# is about curation *this* run moved, and a re-run that named the same drops again would
	# be describing loss that never happened.
	done = set(frappe.get_all("Dock Module", filters={"parenttype": "User"}, pluck="parent", distinct=True))

	# user -> module -> the workspace that claimed it. Insertion order *is* the dock order, so
	# there is no second list to keep in step with this one.
	curated: dict[str, dict[str, str]] = {}
	folded: list[tuple[str, str, str]] = []
	unmapped: list[tuple[str, str, str]] = []

	for row in rows:
		if row.parent in done:
			continue

		module = modules.get(row.workspace)
		if not module:
			why = "no such workspace" if row.workspace not in modules else "workspace has no module"
			unmapped.append((row.parent, row.workspace, why))
			continue

		claimed = curated.setdefault(row.parent, {})
		if module in claimed:
			folded.append((row.parent, row.workspace, f"{module}, already curated via '{claimed[module]}'"))
			continue

		claimed[module] = row.workspace

	entries = 0
	for user, claimed in curated.items():
		for idx, module in enumerate(claimed, start=1):
			frappe.get_doc(
				{
					"doctype": "Dock Module",
					"parenttype": "User",
					"parentfield": "dock_modules",
					"parent": user,
					"module": module,
					"idx": idx,
				}
			).db_insert()
		entries += len(claimed)

	report(len(curated), entries, folded, unmapped)


def report(users: int, entries: int, folded: list[tuple], unmapped: list[tuple]):
	"""Say what moved and what did not. Every line here is somebody's own arrangement."""
	for user, workspace, note in folded:
		click.secho(f"  deduplicated {user}: '{workspace}' -> {note}", fg="yellow")
	for user, workspace, why in unmapped:
		click.secho(f"  dropped {user}: '{workspace}' -- {why}", fg="red")

	if users:
		click.secho(f"Migrated {entries} dock module(s) for {users} user(s).", fg="green")
	if folded:
		click.secho(f"{len(folded)} curated workspace(s) shared a module and were deduplicated.", fg="yellow")
	if unmapped:
		click.secho(f"{len(unmapped)} curated workspace(s) could not be mapped to a module.", fg="red")
