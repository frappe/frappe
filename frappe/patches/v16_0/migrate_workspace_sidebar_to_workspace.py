import click

import frappe

# Child fields carried over verbatim when re-parenting `Workspace Sidebar Item` rows
# from `Workspace Sidebar.items` to `Workspace.sidebar_items`.
SIDEBAR_ITEM_FIELDS = (
	"type",
	"label",
	"link_type",
	"link_to",
	"icon",
	"child",
	"indent",
	"collapsible",
	"keep_closed",
	"url",
	"show_arrow",
	"filters",
	"route_options",
	"navigate_to_tab",
	"open_in_new_tab",
)


def execute():
	"""Merge `Workspace Sidebar` into `Workspace`.

	For every `Workspace Sidebar` doc, copy its items into the matching `Workspace`'s
	new `sidebar_items` table (mapping `header_icon` -> `icon`, plus `module_onboarding`
	and `standard`). When no `Workspace` matches the sidebar, create one to host the items
	so no sidebar is lost.
	"""
	if not frappe.db.has_column("Workspace", "sidebar_items") and not frappe.db.exists(
		"DocType", "Workspace Sidebar"
	):
		return

	sidebar_names = frappe.get_all("Workspace Sidebar", pluck="name")

	for name in sidebar_names:
		try:
			migrate_sidebar(name)
		except frappe.NameError:
			click.secho(f"There is a doctype with the name {name}")
			click.secho("Change the Workspace Sidebar name to something else")
		except Exception as e:
			frappe.db.rollback()
			click.secho(f"Failed to migrate Workspace Sidebar '{name}' to Workspace", fg="red")
			click.secho(e)
			frappe.log_error(title="Workspace Sidebar migration failed", reference_name=name)

	frappe.db.commit()  # nosemgrep


def migrate_sidebar(name):
	sidebar = frappe.get_doc("Workspace Sidebar", name)

	# Welcome Workspace was never given a sidebar; leave its special-casing untouched.
	if sidebar.title == "Welcome Workspace":
		return

	workspace = get_or_create_workspace(sidebar)

	workspace.set("sidebar_items", [])
	for item in sidebar.items:
		workspace.append("sidebar_items", {field: item.get(field) for field in SIDEBAR_ITEM_FIELDS})

	if sidebar.header_icon:
		workspace.icon = sidebar.header_icon
	if sidebar.module_onboarding:
		workspace.module_onboarding = sidebar.module_onboarding
	workspace.standard = sidebar.standard

	# A standard workspace must carry app + module so it can be exported to files.
	if sidebar.standard:
		workspace = set_app_and_module(workspace, sidebar)
		workspace.standard = 1
	workspace.save(ignore_permissions=True)
	frappe.db.commit()
	# `remove_orphan_entities` (run later in the same migrate) deletes any standard public
	# workspace that has no backing JSON file in an app. `on_update` skips the export during
	# patches, so export through the controller here to give the merged workspace a file.
	if workspace.standard:
		print("Exporting Workspace...", workspace.name, "in", workspace.module)
		workspace.export_workspace()


def set_app_and_module(workspace, sidebar):
	app = sidebar.app or workspace.app
	if not app:
		return

	workspace.app = app
	if not workspace.module:
		modules = frappe.get_module_list(app)
		workspace.module = modules[0] if modules else None
	return workspace


def get_or_create_workspace(sidebar):
	if frappe.db.exists("Workspace", sidebar.title):
		return frappe.get_doc("Workspace", sidebar.title)

	public = 0 if sidebar.for_user else 1
	click.echo(f"Creating Workspace '{sidebar.title}' for orphan Workspace Sidebar")

	workspace = frappe.new_doc("Workspace")
	workspace.update(
		{
			"title": sidebar.title,
			"label": sidebar.title,
			"type": "Workspace",
			"content": "[]",
			"public": public,
			"for_user": sidebar.for_user or "",
			"module": sidebar.module or None,
			"app": sidebar.app,
			"sequence_id": frappe.db.count("Workspace", {"public": public}),
		}
	)
	workspace.save(ignore_permissions=True)
	return workspace
