from collections import Counter

import click

import frappe

CATCH_ALL_MODULE = "Desk"


def execute():
	"""Give every Workspace a module, so `Workspace.module` can become mandatory.

	The dock is module-shaped now, so a workspace with no module belongs nowhere: it cannot
	appear on any dock and its sidebar items cannot be merged into any module's sidebar.

	Resolution ladder, most to least trustworthy:
	  1. the first module of the workspace's mounted `app`
	  2. the majority module of what its `sidebar_items` link to
	  3. the majority module of what its `links` and `shortcuts` point at
	  4. its `parent_page`'s module
	  5. a catch-all, logged loudly -- someone should look at these
	"""
	workspaces = frappe.get_all(
		"Workspace",
		filters={"module": ["in", ["", None]]},
		fields=["name", "app", "parent_page", "public", "for_user"],
	)
	if not workspaces:
		return

	assigned = Counter()
	for workspace in workspaces:
		module, how = resolve_module(workspace)
		frappe.db.set_value("Workspace", workspace.name, "module", module, update_modified=False)
		assigned[how] += 1

		colour = "red" if how == "catch-all" else None
		click.secho(f"  {workspace.name} -> {module} ({how})", fg=colour)

	click.secho(
		f"Backfilled Workspace.module for {len(workspaces)} workspace(s): "
		+ ", ".join(f"{how} {n}" for how, n in assigned.items()),
		fg="yellow" if assigned.get("catch-all") else "green",
	)


def resolve_module(workspace) -> tuple[str, str]:
	if workspace.app:
		modules = frappe.get_all("Module Def", filters={"app_name": workspace.app}, pluck="name")
		if modules:
			declared = frappe.get_module_list(workspace.app) if workspace.app else []
			return (declared[0] if declared else sorted(modules)[0]), "app"

	module = majority_module_of_sidebar_items(workspace.name)
	if module:
		return module, "sidebar items"

	module = majority_module_of_widgets(workspace.name)
	if module:
		return module, "links/shortcuts"

	if workspace.parent_page:
		module = frappe.db.get_value("Workspace", workspace.parent_page, "module")
		if module:
			return module, "parent page"

	return ensure_catch_all(), "catch-all"


def majority_module_of_sidebar_items(workspace: str) -> str | None:
	rows = frappe.get_all(
		"Workspace Sidebar Item",
		filters={"parenttype": "Workspace", "parentfield": "sidebar_items", "parent": workspace},
		fields=["link_type", "link_to"],
	)
	return majority_module([(r.link_type, r.link_to) for r in rows])


def majority_module_of_widgets(workspace: str) -> str | None:
	targets = []
	for doctype, type_field in (("Workspace Link", "link_type"), ("Workspace Shortcut", "type")):
		if not frappe.db.exists("DocType", doctype):
			continue
		for row in frappe.get_all(
			doctype, filters={"parent": workspace}, fields=[f"{type_field} as link_type", "link_to"]
		):
			targets.append((row.link_type, row.link_to))
	return majority_module(targets)


def majority_module(targets) -> str | None:
	"""The module most of these link targets belong to, ignoring what can't be resolved."""
	modules = []
	for link_type, link_to in targets:
		if not link_to or link_type in (None, "URL"):
			continue
		if not frappe.db.exists("DocType", link_type):
			continue
		module = frappe.db.get_value(link_type, link_to, "module")
		if module:
			modules.append(module)

	counts = Counter(modules)
	return counts.most_common(1)[0][0] if counts else None


def ensure_catch_all() -> str:
	if not frappe.db.exists("Module Def", CATCH_ALL_MODULE):
		frappe.get_doc(
			{"doctype": "Module Def", "module_name": CATCH_ALL_MODULE, "app_name": "frappe"}
		).insert(ignore_permissions=True)
	return CATCH_ALL_MODULE
