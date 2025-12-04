# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

import os
from json import JSONDecodeError, dumps, loads

import click

import frappe
from frappe import _
from frappe.boot import get_allowed_pages, get_allowed_reports
from frappe.model.document import Document
from frappe.modules.export_file import strip_default_fields
from frappe.modules.utils import create_directory_on_app_path


class WorkspaceSidebar(Document):
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
		title: DF.Data | None
	# end: auto-generated types

	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		if not frappe.flags.in_migrate:
			self.user = frappe.get_user()
			self.can_read = self.get_cached("user_perm_can_read", self.get_can_read_items)

		self.allowed_pages = get_allowed_pages(cache=True)
		self.allowed_reports = get_allowed_reports(cache=True)
		self.restricted_doctypes = frappe.cache.get_value("domain_restricted_doctypes")
		self.restricted_pages = frappe.cache.get_value("domain_restricted_pages")

	def get_can_read_items(self):
		if not self.user.can_read:
			self.user.build_permissions()

	def before_save(self):
		allow_export = self.app and not frappe.flags.in_import and frappe.conf.developer_mode
		if allow_export:
			self.export_sidebar()
		self.set_module()

	def export_sidebar(self):
		folder_path = create_directory_on_app_path("workspace_sidebar", self.app)
		file_path = os.path.join(folder_path, f"{frappe.scrub(self.title)}.json")
		doc_export = self.as_dict(no_nulls=True, no_private_properties=True)
		doc_export = strip_default_fields(self, doc_export)
		with open(file_path, "w+") as doc_file:
			doc_file.write(frappe.as_json(doc_export) + "\n")

	def delete_file(self):
		folder_path = create_directory_on_app_path("workspace_sidebar", self.app)
		file_path = os.path.join(folder_path, f"{frappe.scrub(self.title)}.json")
		if os.path.exists(file_path):
			os.remove(file_path)

	def on_trash(self):
		if is_workspace_manager():
			if frappe.conf.developer_mode and self.app:
				self.delete_file()
		else:
			frappe.throw(_("You need to be Workspace Manager to delete a public workspace."))

	def is_item_allowed(self, name, item_type):
		if frappe.session.user == "Administrator":
			return True

		item_type = item_type.lower()

		if item_type == "doctype":
			return (
				name in (self.can_read or [])
				and name in (self.restricted_doctypes or [])
				and frappe.has_permission(name)
			)
		if item_type == "page":
			return name in self.allowed_pages and name in self.restricted_pages
		if item_type == "report":
			return name in self.allowed_reports
		if item_type == "help":
			return True
		if item_type == "dashboard":
			return True
		if item_type == "url":
			return True

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


@frappe.whitelist()
def add_sidebar_items(sidebar_title, sidebar_items):
	sidebar_items = loads(sidebar_items)
	w = frappe.get_doc("Workspace Sidebar", sidebar_title)
	items = []
	current_idx = 1
	for item in sidebar_items:
		si = frappe.new_doc("Workspace Sidebar Item")
		si.update(item)
		items.append(si)
		si.idx = current_idx
		items.append(si)
		current_idx += 1

		nested_items = item.get("nested_items", [])
		if nested_items:
			for nested_item in nested_items:
				new_nested_item = frappe.new_doc("Workspace Sidebar Item")
				new_nested_item.update(nested_item)
				new_nested_item.child = 1
				new_nested_item.idx = current_idx
				items.append(new_nested_item)
				current_idx += 1

	w.items = items
	w.save()
	return w


def add_to_my_workspace(workspace):
	try:
		if not workspace.for_user:
			return

		sidebar_name = f"My Workspaces-{workspace.for_user}"
		existing_sidebar = frappe.db.exists("Workspace Sidebar", sidebar_name)

		if existing_sidebar:
			private_sidebar = frappe.get_doc("Workspace Sidebar", existing_sidebar)
		else:
			# clone sidebar
			base_sidebar = frappe.get_doc("Workspace Sidebar", "My Workspaces")
			private_sidebar = frappe.copy_doc(base_sidebar)
			private_sidebar.title = sidebar_name
			private_sidebar.for_user = workspace.for_user
			private_sidebar.owner = workspace.for_user
			private_sidebar.items = []

		sidebar_item = {
			"label": workspace.title,
			"type": "Link",
			"link_to": f"{workspace.title}-{workspace.for_user}",
			"link_type": "Workspace",
			"icon": workspace.icon,
		}

		private_sidebar.append("items", sidebar_item)

		if existing_sidebar:
			private_sidebar.save()
		else:
			private_sidebar.insert()

	except Exception as e:
		frappe.log_error(title="Error in Adding Private Workspaces", message=e)
