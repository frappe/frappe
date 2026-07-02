# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import os

import click

import frappe
from frappe import _
from frappe.desk.desk_views import DeskViews
from frappe.model.document import Document
from frappe.modules.export_file import strip_default_fields
from frappe.modules.utils import create_directory_on_app_path
from frappe.utils.caching import site_cache

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


class WorkspaceSidebar(Document, DeskViews):
	_DOCTYPE_NAME = "Workspace Sidebar"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.workspace_sidebar_item.workspace_sidebar_item import WorkspaceSidebarItem
		from frappe.types import DF

		app: DF.Autocomplete | None
		for_user: DF.Link | None
		items: DF.Table[WorkspaceSidebarItem]
		module: DF.Text | None
		module_onboarding: DF.Link | None
		standard: DF.Check
		title: DF.Data | None
	# end: auto-generated types

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if not frappe.flags.in_migrate:
			self.user = frappe.get_user()
			self.can_read = self.get_cached("user_perm_can_read", self.get_can_read_items)

	def get_can_read_items(self):
		if not self.user.can_read:
			self.user.build_permissions()

	def before_save(self):
		self.export_sidebar()
		if not self.for_user:
			self.set_module()

	def export_sidebar(self):
		allow_export = (
			self.app and self.standard and not frappe.flags.in_import and frappe.conf.developer_mode
		)
		if allow_export:
			folder_path = create_directory_on_app_path("workspace_sidebar", self.app)
			file_path = os.path.join(folder_path, f"{frappe.scrub(self.title)}.json")
			doc_export = self.as_dict(no_nulls=True, no_private_properties=True)
			doc_export = strip_default_fields(self, doc_export)
			with open(file_path, "w+") as doc_file:
				doc_file.write(frappe.as_json(doc_export) + "\n")

	def on_trash(self):
		if is_workspace_manager():
			if frappe.conf.developer_mode and self.app:
				delete_file(self.app, self.title)
		else:
			frappe.throw(_("You need to be Workspace Manager to delete a public workspace."))

	def after_rename(self, old, new, merge):
		if self.standard:
			delete_file(self.app, old)
			self.export_sidebar()

	def get_cached(self, cache_key, fallback_fn):
		value = frappe.cache.get_value(cache_key, user=frappe.session.user)
		if value is not None:
			return value

		value = fallback_fn()

		# Expire every six hour
		frappe.cache.set_value(cache_key, value, frappe.session.user, 21600)
		return value

	def set_module(self):
		if not self.module:
			self.module = self.get_module_from_items()

	def get_module_from_items(self):
		all_modules_in_sidebars = []

		for item in self.items:
			if item.type != "Section Break" and item.type != "Sidebar Item Group" and item.link_type != "URL":
				try:
					all_modules_in_sidebars.append(frappe.get_doc(item.link_type, item.link_to).module)
				except frappe.DoesNotExistError as e:
					frappe.logger().error(e)
		from collections import Counter

		counts = Counter(all_modules_in_sidebars)
		if counts and counts.most_common(1)[0]:
			return counts.most_common(1)[0][0]

	@frappe.whitelist()
	def migrate_to_workspace(self):
		"""Merge this `Workspace Sidebar` into its matching `Workspace`.

		Copies the sidebar items into the matching `Workspace`'s `sidebar_items` table
		(mapping `header_icon` -> `icon`, plus `module_onboarding` and `standard`). When no
		`Workspace` matches the sidebar, one is created to host the items so no sidebar is lost.
		"""
		if not is_workspace_manager():
			frappe.throw(
				_("You need to be Workspace Manager to migrate a sidebar."),
				frappe.PermissionError,
			)

		# Welcome Workspace was never given a sidebar; leave its special-casing untouched.
		if self.title == "Welcome Workspace":
			return

		workspace = get_or_create_workspace(self)

		workspace.set("sidebar_items", [])
		for item in self.items:
			workspace.append("sidebar_items", {field: item.get(field) for field in SIDEBAR_ITEM_FIELDS})

		if self.header_icon:
			workspace.icon = self.header_icon
		if self.module_onboarding:
			workspace.module_onboarding = self.module_onboarding
		workspace.standard = self.standard

		# A standard workspace must carry app + module so it can be exported to files. If no app
		# can be resolved it can't be exported, so keep it as a non-standard workspace instead.
		if self.standard:
			set_app_and_module(workspace, self)
			workspace.standard = 1 if workspace.module else 0

		workspace.save(ignore_permissions=True)
		frappe.db.commit()  # nosemgrep
		# `remove_orphan_entities` (run later during migrate) deletes any standard public
		# workspace that has no backing JSON file in an app. `on_update` skips the export during
		# patches, so export through the controller here to give the merged workspace a file.
		if workspace.standard:
			workspace.export_workspace()

		return workspace


def set_app_and_module(workspace, sidebar):
	"""Populate `app`/`module` on `workspace` in place. No-op when no app can be resolved."""
	app = sidebar.app or workspace.app
	if not app:
		return

	workspace.app = app
	if not workspace.module:
		modules = frappe.get_module_list(app)
		workspace.module = modules[0] if modules else None


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


def delete_file(app, title):
	folder_path = create_directory_on_app_path("workspace_sidebar", app)
	file_path = os.path.join(folder_path, f"{frappe.scrub(title)}.json")
	if os.path.exists(file_path):
		os.remove(file_path)


def is_workspace_manager():
	return "Workspace Manager" in frappe.get_roles()


def create_workspace_sidebar_for_workspaces():
	from frappe.query_builder import DocType

	workspace = DocType("Workspace")

	all_workspaces = (
		frappe.qb.from_(workspace)
		.select(workspace.name)
		.where((workspace.public == 1) & (workspace.name != "Welcome Workspace"))
	).run(pluck=True)

	existing_sidebars = frappe.get_all("Workspace Sidebar", pluck="title")
	for workspace in all_workspaces:
		if workspace not in existing_sidebars:
			workspace_doc = frappe.get_doc("Workspace", workspace)
			sidebar = frappe.new_doc("Workspace Sidebar")
			sidebar.title = workspace
			sidebar.header_icon = frappe.db.get_value("Workspace", workspace, "icon")
			click.echo(f"Creating Sidebar Items for {workspace}")
			shortcuts = workspace_doc.shortcuts

			items = []
			idx = 1
			# Adding the workspace itself as home
			workspace_sidebar_item = frappe.new_doc("Workspace Sidebar Item")
			workspace_sidebar_item.update(
				{"label": "Home", "link_to": workspace, "link_type": "Workspace", "type": "Link", "idx": 0}
			)
			items.append(workspace_sidebar_item)
			# Process Shortcuts
			for s in shortcuts:
				workspace_sidebar_item = frappe.new_doc("Workspace Sidebar Item")
				workspace_sidebar_item.update(
					{"label": s.label, "link_to": s.link_to, "link_type": s.type, "type": "Link", "idx": idx}
				)
				items.append(workspace_sidebar_item)
				idx += 1
			try:
				sidebar.items = items
				sidebar.save()
			except Exception as e:
				frappe.log_error(title="Failed To Create Sidebar", message=e)


@site_cache()
def auto_generate_sidebar_from_module():
	"""Auto generate sidebar from module"""
	sidebars = []
	for module in frappe.get_all("Module Def", pluck="name"):
		# Skip modules whose public workspace already carries authored sidebar items -- that
		# workspace's sidebar is built from `Workspace.sidebar_items` (the source of truth), so a
		# generated fallback would be redundant.
		if not module_has_workspace_sidebar(module):
			try:
				module_info = get_module_info(module)
				sidebar_items = create_sidebar_items(module_info)
				sidebar = frappe.new_doc("Workspace Sidebar")
				sidebar.title = module
				sidebar.items = sidebar_items
				sidebar.module = module
				sidebar.header_icon = "hammer"

				sidebar.app = frappe.modules.utils.get_module_app(module)
				# in-memory marker (not a persisted field): flags sidebars built from a module so the
				# desk can render a generated avatar instead of the default app-logo header icon.
				sidebar.from_module = 1
				sidebars.append(sidebar)
			except frappe.DoesNotExistError:
				pass
	return sidebars


def module_has_workspace_sidebar(module):
	"""Whether a public Workspace for this module already carries authored sidebar items."""
	workspaces = frappe.get_all("Workspace", {"module": module, "public": 1}, pluck="name")
	if not workspaces:
		return False
	return bool(
		frappe.db.exists(
			"Workspace Sidebar Item",
			{"parenttype": "Workspace", "parentfield": "sidebar_items", "parent": ["in", workspaces]},
		)
	)


def get_module_info(module_name):
	entities = ["Workspace", "Dashboard", "DocType", "Report", "Page"]
	module_info = {}

	for entity in entities:
		module_info[entity] = {}
		filters = [{"module": module_name}]
		pluck = "name"
		fieldnames = ["name"]
		if entity.lower() == "doctype":
			filters.append({"istable": 0})
		if entity.lower() == "workspace":
			# only surface public workspaces; private ones belong to individual users
			filters.append({"public": 1})
		if entity.lower() == "page":
			fieldnames.append("title")
			pluck = None
		module_info[entity] = frappe.get_all(
			entity, filters=filters, fields=fieldnames, pluck=pluck, order_by="creation asc"
		)

	# if module info has no workspaces, then move doctypes to the front
	if not module_info.get("Workspace"):
		module_info = {
			"DocType": module_info.get("DocType"),
			"Workspace": module_info.get("Workspace"),
			"Report": module_info.get("Report"),
			"Dashboard": module_info.get("Dashboard"),
			"Page": module_info.get("Page"),
		}
	doctype_limit = 3
	module_info["DocType"] = (module_info.get("DocType") or [])[:doctype_limit]
	return module_info


def create_sidebar_items(module_info):
	sidebar_items = []
	idx = 1

	section_entities = {"report": "Reports", "dashboard": "Dashboards", "page": "Pages"}

	for entity, items in module_info.items():
		section_break_added = False
		entity_lower = entity.lower()

		if entity_lower in section_entities:
			section_break = []
			if entity_lower == "report":
				section_break = add_section_breaks("Reports", idx)
			elif entity_lower in ("dashboard", "page") and len(items) > 1:
				section_break = add_section_breaks(section_entities[entity_lower], idx)
				section_break_added = True
			if section_break:
				sidebar_items.append(section_break)
			idx += 1

		for item in items:
			item_info = {"label": item, "type": "Link", "link_type": entity, "link_to": item, "idx": idx}

			if entity_lower == "report":
				item_info["child"] = 1
				item_info["icon"] = "table"

			if entity_lower == "page":
				item_info["label"] = item.get("title")
				item_info["link_to"] = item.get("name")

			if entity_lower == "workspace":
				item_info["icon"] = "home"
				item_info["icon"] = "wallpaper"

			if entity_lower == "page":
				item_info["icon"] = "panel-top"

			if entity_lower == "doctype" and "settings" in item.lower():
				item_info["icon"] = "settings"

			if section_break_added:
				item_info["child"] = 1

			sidebar_item = frappe.new_doc("Workspace Sidebar Item")
			sidebar_item.update(item_info)
			sidebar_items.append(sidebar_item)

			idx += 1

	return sidebar_items


def add_section_breaks(label, idx):
	section_break = frappe.new_doc("Workspace Sidebar Item")
	section_break.update({"label": label, "type": "Section Break", "idx": idx})
	return section_break
