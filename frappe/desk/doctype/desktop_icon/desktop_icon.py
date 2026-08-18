# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json
import os
import random

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.modules.export_file import strip_default_fields
from frappe.modules.import_file import import_file_by_path
from frappe.modules.utils import create_directory_on_app_path, get_app_level_directory_path


class DesktopIcon(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.has_role.has_role import HasRole
		from frappe.types import DF

		app: DF.Autocomplete | None
		bg_color: DF.Literal["gray", "blue"]
		hidden: DF.Check
		icon: DF.Icon | None
		icon_image: DF.Attach | None
		icon_type: DF.Literal["Link", "Folder", "App"]
		idx: DF.Int
		label: DF.Data | None
		link: DF.SmallText | None
		link_to: DF.DynamicLink | None
		link_type: DF.Literal["Workspace Sidebar", "External"]
		logo_url: DF.Data | None
		parent_icon: DF.Link | None
		restrict_removal: DF.Check
		roles: DF.Table[HasRole]
		sidebar: DF.Link | None
		standard: DF.Check
	# end: auto-generated types

	def validate(self):
		if not self.label:
			self.label = self.module_name

	def on_trash(self):
		clear_desktop_icons_cache()
		if frappe.conf.developer_mode and self.standard and self.app:
			delete_desktop_icon_file(self.app, self.label)

	def check_for_restrict_removal(self):
		if self.restrict_removal:
			frappe.throw(_("Cannot delete Desktop Icon '{0}' as it is restricted").format(self.label))

	def on_update(self):
		self.export_desktop_icon()
		if self.standard:
			frappe.cache.delete_key("desktop_icons")
			frappe.cache.delete_key("bootinfo")
		else:
			clear_desktop_icons_cache(user=self.owner)

	def after_rename(self, old, new, merge):
		if self.standard and self.app:
			delete_desktop_icon_file(self.app, old)
			self.export_desktop_icon()

	def export_desktop_icon(self):
		allow_export = (
			self.standard and self.app and not frappe.flags.in_import and frappe.conf.developer_mode
		)
		if allow_export:
			folder_path = create_directory_on_app_path("desktop_icon", self.app)
			file_path = os.path.join(folder_path, f"{frappe.scrub(self.label)}.json")
			doc_export = self.as_dict(no_nulls=True, no_private_properties=True)
			strip_default_fields(self, doc_export)
			with open(file_path, "w+") as icon_file_doc:
				icon_file_doc.write(frappe.as_json(doc_export) + "\n")

	def delete_desktop_icon_file(self):
		folder_path = create_directory_on_app_path("desktop_icon", self.app)
		file_path = os.path.join(folder_path, f"{frappe.scrub(self.label)}.json")
		if os.path.exists(file_path):
			os.remove(file_path)

	def after_insert(self):
		clear_desktop_icons_cache()


def delete_desktop_icon_file(app, label):
	folder_path = create_directory_on_app_path("desktop_icon", app)
	file_path = os.path.join(folder_path, f"{frappe.scrub(label)}.json")
	if os.path.exists(file_path):
		os.remove(file_path)


def get_workspace_names(workspaces):
	workspace_list = []
	for w in workspaces["pages"]:
		workspace_list.append(w["name"])
	return workspace_list


def check_app_permission(label, app):
	for a in frappe.get_installed_apps():
		if frappe.get_hooks(app_name=a)["app_title"][0] == label or app == a:
			app_detail = frappe.get_hooks("add_to_apps_screen", app_name=a)
			if len(app_detail) != 0:
				permission_method = app_detail[0].get("has_permission", None)
				if permission_method:
					return frappe.call(permission_method)
				else:
					return True
			else:
				# App hooks.py doesn't have add_to_apps_screen
				return True


def get_desktop_icons(user=None, bootinfo=None):
	"""Return desktop icons for user"""
	if not user:
		user = frappe.session.user

	user_icons = frappe.cache.hget("desktop_icons", user)

	if not user_icons:
		fields = [
			"label",
			"bg_color",
			"link",
			"link_type",
			"app",
			"icon_type",
			"parent_icon",
			"icon",
			"link_to",
			"idx",
			"standard",
			"logo_url",
			"hidden",
			"name",
			"restrict_removal",
			"icon_image",
		]

		from frappe.query_builder import DocType

		DesktopIcon = DocType("Desktop Icon")

		user_icons = (
			frappe.qb.from_(DesktopIcon)
			.select(*fields)
			.where(
				(DesktopIcon.standard == 1)
				| (
					(DesktopIcon.standard == 0)
					& (DesktopIcon.owner.isin(["Administrator", frappe.session.user]))
				)
			)
			.distinct()
		).run(as_dict=True)

		# sort by idx
		user_icons.sort(key=lambda a: a.idx)

		# map of Desktop Icon name -> set of roles configured in its `roles` child table,
		# scoped to the icons we actually loaded for this user
		icon_roles_map = {}
		icon_names = [s.name for s in user_icons]
		if icon_names:
			icon_roles = frappe.get_all(
				"Has Role",
				filters={"parenttype": "Desktop Icon", "parent": ["in", icon_names]},
				fields=["parent", "role"],
			)
			for r in icon_roles:
				icon_roles_map.setdefault(r.parent, set()).add(r.role)

		user_roles = set(frappe.get_roles(user))

		permitted_icons = []
		permitted_parent_labels = set()
		if bootinfo:
			for s in user_icons:
				if s.icon_type == "Folder":
					permitted = True
				elif s.icon_type == "App":
					permitted = check_app_permission(s.label, s.app)
				else:
					# Workspace Sidebar link: present in the boot map ⇒ user can see at least
					# one item in it (get_sidebar_items already enforces this).
					sidebar = bootinfo.workspace_sidebar_item.get(s.label.lower())
					permitted = bool(sidebar and sidebar["items"])

				# if the icon restricts by role, the user must have at least one of them
				if permitted and icon_roles_map.get(s.name):
					permitted = bool(icon_roles_map[s.name] & user_roles)

				if permitted:
					permitted_icons.append(s)

					if not s.parent_icon:
						permitted_parent_labels.add(s.label)

		user_icons = [
			s for s in permitted_icons if not s.parent_icon or s.parent_icon in permitted_parent_labels
		]

		frappe.cache.hset("desktop_icons", user, user_icons)
	return user_icons


def clear_desktop_icons_cache(user=None):
	frappe.cache.hdel("desktop_icons", user or frappe.session.user)
	frappe.cache.hdel("bootinfo", user or frappe.session.user)


def get_app_desktop_icon(app_name: str) -> str | None:
	"""Return the name of the "App" type Desktop Icon created for `app_name`, if it exists."""
	app_title = frappe.get_hooks("app_title", app_name=app_name)
	if not app_title:
		return None

	return frappe.db.exists("Desktop Icon", {"label": app_title[0], "icon_type": "App"})


def create_desktop_icons_from_workspace():
	workspaces = frappe.get_all(
		"Workspace",
		filters={"public": 1, "name": ["!=", "Welcome Workspace"]},
		fields=["name", "icon", "app", "module"],
	)

	for w in workspaces:
		icon = frappe.new_doc("Desktop Icon")
		icon.link_type = "Workspace Sidebar"
		icon.label = w.name
		icon.icon_type = "Link"
		icon.link_to = w.name
		icon.icon = w.icon
		if w.module:
			app_name = w.app or frappe.db.get_value("Module Def", w.module, "app_name")
			if app_name in frappe.get_installed_apps():
				icon.app_name = app_name
				app_title = frappe.get_hooks("app_title", app_name=app_name)[0]
				app_icon = get_app_desktop_icon(app_name)
				if app_icon:
					icon.parent_icon = app_icon

				app_icon_link = frappe.db.get_value("Desktop Icon", app_icon, "link") if app_icon else None

				# Portal App With Desk Workspace
				if app_icon_link and not app_icon_link.startswith("/app"):
					icon.hidden = 1
					icon.parent_icon = None

				# If Desk App has one workspace with the same name
				if icon.label == app_title and app_icon_link and app_icon_link.startswith("/app"):
					icon.hidden = 1
					icon.parent_icon = None

				try:
					# `label` is the docname (autoname: field:label) and is unique, so an icon
					# of *any* type with this label collides. Filtering on icon_type as well
					# would let a workspace named after an app slip through into an IntegrityError.
					if not frappe.db.exists("Desktop Icon", icon.label):
						icon.insert(ignore_if_duplicate=True)
				except Exception:
					frappe.log_error(title="Creation of Desktop Icon Failed")


def create_desktop_icons_from_installed_apps():
	apps = frappe.get_installed_apps()
	index = 0
	for a in apps:
		if get_app_desktop_icon(a):
			continue

		app_details = frappe.get_hooks("add_to_apps_screen", app_name=a)
		if len(app_details) != 0:
			app_title = frappe.get_hooks("app_title", app_name=a)[0]
			if frappe.db.exists("Desktop Icon", app_title):
				# some other icon (e.g. a workspace link) already holds this label
				continue

			icon = frappe.new_doc("Desktop Icon")
			icon.label = app_title
			icon.link_type = "External"
			icon.idx = index
			icon.icon_type = "App"
			icon.app = a
			icon.link = app_details[0]["route"]
			icon.logo_url = app_details[0]["logo"]
			icon.save()
			index += 1


def create_desktop_icons():
	create_desktop_icons_from_installed_apps()
	create_desktop_icons_from_workspace()


def create_user_icons(user, data):
	user_settings = json.loads(data)
	new_icons = user_settings.get("icons_to_create")
	if new_icons:
		new_icons = json.loads(user_settings.get("icons_to_create"))
		if new_icons:
			for icon in new_icons:
				try:
					desktop_icon = frappe.new_doc("Desktop Icon")
					desktop_icon.update(icon)
					desktop_icon.owner = user
					desktop_icon.save()
				except Exception as e:
					frappe.log_error("Error in syncing icons", e)
			user_settings.pop("icons_to_create", None)
			frappe.cache.hset("_user_settings", f"{'Desktop Icon'}::{user}", json.dumps(user_settings))
			return json.dumps(user_settings)
	return data


@frappe.whitelist()
def add_workspace_to_desktop(workspace: str):
	if frappe.db.exists("Workspace Sidebar", workspace):
		sidebar = frappe.get_doc("Workspace Sidebar", workspace)
	else:
		sidebar = frappe.new_doc("Workspace Sidebar")
		sidebar.title = workspace

	if not any(item.link_to == workspace for item in sidebar.get("items", [])):
		sidebar_item = frappe.new_doc("Workspace Sidebar Item")
		sidebar_item.label = workspace
		sidebar_item.type = "Link"
		sidebar_item.link_to = workspace
		sidebar_item.link_type = "Workspace"
		sidebar.append("items", sidebar_item)
		sidebar.save()

	if frappe.db.exists("Desktop Icon", workspace):
		return {"icon": frappe.get_doc("Desktop Icon", workspace).as_dict()}

	new_icon = frappe.new_doc("Desktop Icon")
	new_icon.label = workspace
	new_icon.icon_type = "Link"
	new_icon.link_to = workspace
	new_icon.link_type = "Workspace Sidebar"
	new_icon.insert()
	return {"icon": new_icon.as_dict()}
