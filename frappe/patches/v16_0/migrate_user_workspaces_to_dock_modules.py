import click

import frappe


def execute():
	"""Carry each user's dock curation from `User.workspaces` to `User.dock_modules`.

	The dock now lists modules, so a curation stored as workspace names has to be mapped
	through `Workspace.module`. Several curated workspaces can share a module -- that is the
	whole point of the merge -- so the result is deduped, keeping first-seen order.

	A curated workspace with no module is dropped: there is nothing to map it to, and the
	fallback for an empty curation is "show all of the app's modules", which is the safe
	outcome. (`Workspace.module` becomes mandatory in a later phase; until then this is
	possible.)
	"""
	if not frappe.db.exists("DocType", "User Dock Module"):
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

	by_user = {}
	for row in rows:
		module = modules.get(row.workspace)
		if not module:
			continue
		by_user.setdefault(row.parent, [])
		if module not in by_user[row.parent]:
			by_user[row.parent].append(module)

	migrated = 0
	for user, user_modules in by_user.items():
		if frappe.db.exists("User Dock Module", {"parenttype": "User", "parent": user}):
			continue
		for idx, module in enumerate(user_modules, start=1):
			frappe.get_doc(
				{
					"doctype": "User Dock Module",
					"parenttype": "User",
					"parentfield": "dock_modules",
					"parent": user,
					"module": module,
					"idx": idx,
				}
			).db_insert()
		migrated += 1

	if migrated:
		click.secho(f"Migrated dock curation for {migrated} user(s) to modules.", fg="green")
