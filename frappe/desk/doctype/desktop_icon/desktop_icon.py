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
		hidden: DF.Check
		icon_type: DF.Literal["Folder", "App", "Link"]
		idx: DF.Int
		label: DF.Data | None
		link: DF.SmallText | None
		link_to: DF.DynamicLink | None
		link_type: DF.Literal["DocType", "Workspace", "External"]
		logo_url: DF.Data | None
		parent_icon: DF.Link | None
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
			self.delete_desktop_icon_file()

	def on_update(self):
		allow_export = (
			self.standard and self.app and not frappe.flags.in_import and frappe.conf.developer_mode
		)
		if allow_export:
			self.export_desktop_icon()

	def export_desktop_icon(self):
		folder_path = create_directory_on_app_path("desktop_icon", self.app)
		file_path = os.path.join(folder_path, f"{frappe.scrub(self.label)}.json")
		doc_export = self.as_dict(no_nulls=True, no_private_properties=True)
		strip_default_fields(self, doc_export)
		# if self.parent_icon:
		# 	print(self.parent_icon)
		# 	doc_export["parent_icon"] = frappe.db.get_value("Desktop Icon", self.parent_icon, "label")
		with open(file_path, "w+") as icon_file_doc:
			icon_file_doc.write(frappe.as_json(doc_export) + "\n")

	def delete_desktop_icon_file(self):
		folder_path = create_directory_on_app_path("desktop_icon", self.app)
		file_path = os.path.join(folder_path, f"{frappe.scrub(self.label)}.json")
		if os.path.exists(file_path):
			os.remove(file_path)

	def is_permitted(self, bootinfo):
		if frappe.session.user == "Administrator":
			return True
		if self.icon_type == "Folder":
			return True
		workspaces = get_workspace_names(bootinfo.workspaces)
		if self.icon_type == "Link":
			if self.link_type == "DocType":
				return self.link_to in bootinfo.user.can_read
			elif self.link_type == "Workspace":
				return self.link_to in workspaces
		elif self.icon_type == "App":
			return self.check_app_permission(self.label)

	def check_app_permission(self, app_name):
		for a in frappe.get_installed_apps():
			if frappe.get_hooks(app_name=a)["app_title"][0] == app_name or self.app == a:
				permission_method = frappe.get_hooks(app_name=a)["add_to_apps_screen"][0].get(
					"has_permission", None
				)
				if permission_method:
					return frappe.call(permission_method)
				else:
					return True

	# def is_permitted(self):
	# 	"""Return True if `Has Role` is not set or the user is allowed."""
	# 	from frappe.utils import has_common

	# 	allowed = [d.role for d in frappe.get_all("Has Role", fields=["role"], filters={"parent": self.name})]

	# 	if not allowed:
	# 		return True

	# 	roles = frappe.get_roles()

	# 	if has_common(roles, allowed):
	# 		return True

	def after_insert(self):
		clear_desktop_icons_cache()


def get_workspace_names(workspaces):
	workspace_list = []
	for w in workspaces["pages"]:
		workspace_list.append(w["name"])
	return workspace_list


def get_desktop_icons(user=None, bootinfo=None):
	"""Return desktop icons for user"""
	if not user:
		user = frappe.session.user

	user_icons = frappe.cache.hget("desktop_icons", user)

	if not user_icons:
		fields = [
			"label",
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
			"sidebar",
		]

		active_domains = frappe.get_active_domains()

		DocType = frappe.qb.DocType("DocType")
		if active_domains:
			blocked_condition = (
				(DocType.restrict_to_domain.isnull())
				| (DocType.restrict_to_domain == "")
				| (DocType.restrict_to_domain.notin(active_domains))
			)
		else:
			blocked_condition = (DocType.restrict_to_domain.isnull()) | (DocType.restrict_to_domain == "")
		blocked_doctypes = [
			d.get("name")
			for d in frappe.qb.from_(DocType).select(DocType.name).where(blocked_condition).run(as_dict=True)
		]

		standard_icons = frappe.get_all("Desktop Icon", fields=fields, filters={"standard": 1})

		standard_map = {}

		for icon in standard_icons:
			if icon._doctype in blocked_doctypes:
				icon.blocked = 1
			standard_map[icon.module_name] = icon

		user_icons = frappe.get_all("Desktop Icon", fields=fields, filters={"standard": 0, "owner": user})

		# update hidden property
		for icon in user_icons:
			standard_icon = standard_map.get(icon.module_name, None)

			if icon._doctype in blocked_doctypes:
				icon.blocked = 1

			# override properties from standard icon
			if standard_icon:
				for key in ("route", "label", "color", "icon", "link"):
					if standard_icon.get(key):
						icon[key] = standard_icon.get(key)

				if standard_icon.blocked:
					icon.hidden = 1

					# flag for modules_select dialog
					icon.hidden_in_standard = 1

				elif standard_icon.force_show:
					icon.hidden = 0

		# add missing standard icons (added via new install apps?)
		user_icon_names = [icon.module_name for icon in user_icons]
		for standard_icon in standard_icons:
			if standard_icon.module_name not in user_icon_names:
				# if blocked, hidden too!
				if standard_icon.blocked:
					standard_icon.hidden = 1
					standard_icon.hidden_in_standard = 1

				user_icons.append(standard_icon)

		user_blocked_modules = frappe.get_lazy_doc("User", user).get_blocked_modules()
		for icon in user_icons:
			if icon.module_name in user_blocked_modules:
				icon.hidden = 1

		# sort by idx
		user_icons.sort(key=lambda a: a.idx)

		# translate
		# for d in user_icons:
		# 	if d.label:
		# 		d.label = _(d.label, context=d.parent)
		# includes
		permitted_icons = []
		permitted_parent_labels = set()

		if bootinfo:
			for s in user_icons:
				icon = frappe.get_doc("Desktop Icon", s)
				if icon.is_permitted(bootinfo):
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


def create_desktop_icons_from_workspace():
	workspaces = frappe.get_all(
		"Workspace",
		filters={"public": 1, "name": ["!=", "Welcome Workspace"]},
		fields=["name", "icon", "app", "module"],
	)

	for w in workspaces:
		icon = frappe.new_doc("Desktop Icon")
		icon.link_type = "Workspace"
		icon.label = w.name
		icon.icon_type = "Link"
		icon.standard = 1
		icon.link_to = w.name
		icon.icon = w.icon
		if w.module:
			app_name = w.app or frappe.db.get_value("Module Def", w.module, "app_name")
			if app_name in frappe.get_installed_apps():
				icon.app_name = app_name
				app_title = frappe.get_hooks("app_title", app_name=app_name)[0]
				app_icon = frappe.db.exists("Desktop Icon", {"label": app_title, "icon_type": "App"})
				if app_icon:
					icon.parent_icon = app_icon

				# Portal App With Desk Workspace
				if frappe.db.get_value("Desktop Icon", app_icon, "link") and not frappe.db.get_value(
					"Desktop Icon", app_icon, "link"
				).startswith("/app"):
					icon.hidden = 1
					icon.parent_icon = None

				# If Desk App has one workspace with the same name
				if icon.label == app_title and (
					app_icon and frappe.db.get_value("Desktop Icon", app_icon, "link").startswith("/app")
				):
					icon.hidden = 1
					icon.parent_icon = None

				try:
					if not frappe.db.exists(
						"Desktop Icon", [{"label": icon.label, "icon_type": icon.icon_type}]
					):
						icon.insert(ignore_if_duplicate=True)
				except Exception as e:
					frappe.error_log(title="Creation of Desktop Icon Failed", message=e)


def create_desktop_icons_from_installed_apps():
	apps = frappe.get_installed_apps()
	index = 0
	for a in apps:
		app_title = frappe.get_hooks("app_title", app_name=a)[0]
		app_details = frappe.get_hooks("add_to_apps_screen", app_name=a)
		if not frappe.db.exists("Desktop Icon", [{"icon_type": "App"}, {"app": a}]):
			if len(app_details) != 0:
				icon = frappe.new_doc("Desktop Icon")
				icon.label = app_title
				icon.link_type = "External"
				icon.standard = 1
				icon.idx = index
				icon.icon_type = "App"
				icon.app = a
				icon.link = app_details[0]["route"]
				icon.logo_url = app_details[0]["logo"]
				if not frappe.db.exists("Desktop Icon", [{"label": icon.label, "icon_type": icon.icon_type}]):
					icon.save()
				index += 1


def create_desktop_icons():
	create_desktop_icons_from_installed_apps()
	create_desktop_icons_from_workspace()
