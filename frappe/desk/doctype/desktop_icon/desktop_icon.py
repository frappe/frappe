# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

"""The icon grid's rows: what a site sees when its desktop page is the grid.

Retiring. It goes with the icon-grid batch, on one of the two triggers written down in
`frappe/desk/RETIRING.md` -- not on a date, and not on its own.
"""

import json
import os
import random

import frappe
from frappe import _
from frappe.desk.doctype.desktop_settings.desktop_settings import is_desktop_icons_page
from frappe.model.document import Document
from frappe.modules.export_file import strip_default_fields
from frappe.modules.import_file import import_file_by_path
from frappe.modules.utils import create_directory_on_app_path, get_app_level_files


class DesktopIcon(Document):
	_DOCTYPE_NAME = "Desktop Icon"

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
		"""Refuse to remove an icon the grid marks as fixed.

		Kept unwired on purpose: `restrict_removal` means what it always meant -- it hides the
		remove affordance in the grid's edit mode -- and calling this from deletion would make
		a workspace that deletes fine today start throwing. It stays because it is still the
		right answer for a caller that is genuinely removing an icon *from the grid*.
		"""
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
			with open(file_path, "w+") as icon_file_doc:  # nosempgrep
				icon_file_doc.write(frappe.as_json(doc_export) + "\n")

	def delete_desktop_icon_file(self):
		folder_path = create_directory_on_app_path("desktop_icon", self.app)
		file_path = os.path.join(folder_path, f"{frappe.scrub(self.label)}.json")
		if os.path.exists(file_path):
			os.remove(file_path)

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


def is_icon_permitted(icon, bootinfo, roles: list[str], icon_module: str | None) -> bool:
	"""Whether `icon` belongs on this user's desktop.

	Takes a plain icon row rather than a Document, along with the two related bits the check
	needs -- the icon's `Has Role` rows and, for a workspace link, that workspace's module --
	so `get_desktop_icons` can fetch both for the whole grid in one query each instead of
	loading every icon just to reach them.
	"""
	from frappe.desk.doctype.sidebar.sidebar import sidebar_for_module
	from frappe.utils.modules import is_module_visible

	# module permission check
	if icon_module and not is_module_visible(icon_module):
		return False

	# perform a permission check based on roles table (desktop icons)
	if roles and not set(roles).intersection(frappe.get_roles()):
		return False

	if icon.icon_type == "Folder":
		return True
	elif icon.icon_type == "App":
		return _has_app_permission(icon)
	else:
		# Mirrors the boot builder's rule: a sidebar the user can see nothing real in is one
		# they cannot use, so its icon does not belong on the desktop either. The two must not
		# drift -- an icon for an empty sidebar leads nowhere.
		# An icon names a module, and the payload is keyed by shell, so the module has to be
		# resolved to the shell it leads to. The naming rule answers it directly for every
		# sidebar nobody renamed; `sidebar_for_module` covers the rest.
		sidebar = sidebar_for_module(bootinfo.module_sidebars or {}, icon_module or icon.label)
		if not sidebar:
			return False

		items = sidebar["items"]
		return bool(items) and any(item["type"] != "Section Break" for item in items)


def _has_app_permission(icon) -> bool:
	for a in frappe.get_active_apps():
		# an app needn't declare `app_title`; asking for the hook by name returns [] instead
		# of raising, so one such app can't abort the whole grid's permission check
		app_title = (frappe.get_hooks("app_title", app_name=a) or [None])[0]
		if app_title == icon.label or icon.app == a:
			app_detail = frappe.get_hooks("add_to_apps_screen", app_name=a)
			if len(app_detail) != 0:
				permission_method = app_detail[0].get("has_permission", None)
				if permission_method:
					return frappe.get_attr(permission_method)()
				else:
					return True
			else:
				# App hooks.py doesn't have add_to_apps_screen
				return True

	# No installed app matches this icon's app/label (e.g. a leftover icon for an
	# uninstalled app). Return an explicit bool rather than falling through to None,
	# which is_icon_permitted would read the same way but is easy to misread as "unset".
	return False


def get_roles_by_icon(icons: list[dict]) -> dict[str, list[str]]:
	"""The `Has Role` rows of `icons`, as icon name -> the roles it is restricted to."""
	if not icons:
		return {}

	roles_by_icon = {}
	for row in frappe.get_all(
		"Has Role",
		filters={"parenttype": "Desktop Icon", "parent": ("in", [icon.name for icon in icons])},
		fields=["parent", "role"],
	):
		roles_by_icon.setdefault(row.parent, []).append(row.role)

	return roles_by_icon


def get_linked_workspace_modules(icons: list[dict]) -> dict[str, str]:
	"""The module of the workspace each icon links to, as icon name -> module.

	Only a `Link` icon resolves a workspace, so nothing else gets a module -- an icon of
	another type whose `link_to` happens to name a workspace is left alone, as it was when
	this was looked up per icon.
	"""
	linked = {icon.name: icon.link_to for icon in icons if icon.icon_type == "Link" and icon.link_to}
	if not linked:
		return {}

	modules = dict(
		frappe.get_all(
			"Workspace",
			filters={"name": ("in", list(set(linked.values())))},
			fields=["name", "module"],
			as_list=True,
		)
	)

	return {name: modules.get(workspace) for name, workspace in linked.items()}


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

		permitted_icons = []
		permitted_parent_labels = set()
		if bootinfo:
			# Prefetched for the whole grid: the check runs per icon on every cache miss, and
			# reaching this data through a `frappe.get_doc` each made the boot payload cost a
			# few queries per icon on a page that exists to show a lot of icons.
			roles_by_icon = get_roles_by_icon(user_icons)
			modules_by_icon = get_linked_workspace_modules(user_icons)

			for s in user_icons:
				icon_module = modules_by_icon.get(s.name)
				if is_icon_permitted(
					s,
					bootinfo,
					roles=roles_by_icon.get(s.name, []),
					icon_module=icon_module,
				):
					# carried into the payload so the client resolves the icon's route through
					# the module-keyed sidebar payload instead of guessing from its label
					s.module = icon_module
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
		filters={"public": 1},
		fields=["name", "icon", "module"],
	)

	for w in workspaces:
		icon = frappe.new_doc("Desktop Icon")
		icon.link_type = "Workspace Sidebar"
		icon.label = w.name
		icon.icon_type = "Link"
		icon.link_to = w.name
		icon.icon = w.icon
		if w.module:
			# The module is the only rung left: a workspace stopped carrying its own app when
			# the module became the thing that has one, and asking for the dropped column made
			# this whole loop raise on the first workspace it reached.
			app_name = frappe.db.get_value("Module Def", w.module, "app_name")
			if app_name in frappe.get_installed_apps():
				# `app`, which the doctype has a column for -- `app_name` was silently dropped
				# on save, so every generated row landed appless and invisible to anything
				# that asks an icon which app it came from.
				icon.app = app_name
				# App icons are labelled by `app_title`; an app that declares no such hook has
				# none to parent this workspace icon to, and looking one up by a null label
				# would match whatever unlabelled row happens to exist.
				app_title = (frappe.get_hooks("app_title", app_name=app_name) or [None])[0]
				app_icon = (
					frappe.db.exists("Desktop Icon", {"label": app_title, "icon_type": "App"})
					if app_title
					else None
				)
				if app_icon:
					icon.parent_icon = app_icon

				# Resolve the parent App icon's link once. It can be missing (App icons don't
				# always carry a link), so guard the `.startswith` checks below -- calling it on
				# None raised AttributeError and aborted the whole seeding loop.
				app_link = frappe.db.get_value("Desktop Icon", app_icon, "link") if app_icon else None

				# Portal App With Desk Workspace
				if app_link and not app_link.startswith("/app"):
					icon.hidden = 1
					icon.parent_icon = None

				# If Desk App has one workspace with the same name
				if icon.label == app_title and app_link and app_link.startswith("/app"):
					icon.hidden = 1
					icon.parent_icon = None

				try:
					if not frappe.db.exists(
						"Desktop Icon", [{"label": icon.label, "icon_type": icon.icon_type}]
					):
						# `ignore_links`: `link_to` is a Dynamic Link typed off `link_type`, so
						# it looks for a `Workspace Sidebar` document that no longer exists. The
						# mis-declaration is knowingly retained under D14 and the column is inert
						# -- the client routes the workspace through the sidebar payload -- but
						# validating it would refuse every icon the grid generates.
						icon.insert(ignore_if_duplicate=True, ignore_links=True)
				except Exception:
					# `frappe.error_log` is the request's list of errors, not a function -- calling
					# it turned one unseedable workspace into a TypeError that aborted the loop
					frappe.log_error("Creation of Desktop Icon Failed")


def create_desktop_icons_from_installed_apps():
	apps = frappe.get_installed_apps()
	index = 0
	for a in apps:
		# the icon is named after `app_title` (autoname is `field:label`), so an app that
		# declares no such hook has nothing to name one with -- skip it rather than let an
		# IndexError abort the seeding loop and leave every later app without icons
		app_title = (frappe.get_hooks("app_title", app_name=a) or [None])[0]
		if not app_title:
			continue

		app_details = frappe.get_hooks("add_to_apps_screen", app_name=a)
		if not frappe.db.exists("Desktop Icon", [{"icon_type": "App"}, {"app": a}]):
			if len(app_details) != 0:
				icon = frappe.new_doc("Desktop Icon")
				icon.label = app_title
				icon.link_type = "External"
				icon.idx = index
				icon.icon_type = "App"
				icon.app = a
				icon.link = app_details[0]["route"]
				icon.logo_url = app_details[0]["logo"]
				if not frappe.db.exists("Desktop Icon", [{"label": icon.label, "icon_type": icon.icon_type}]):
					icon.save()
				index += 1


def create_desktop_icons():
	"""Seed Desktop Icons for the Desktop Icon grid.

	Guarded rather than the readers: a site whose desktop page is `Apps` draws that screen
	from the `add_to_apps_screen` hook and never reads these rows, so generating them on
	every app install would be pure accumulation.
	"""
	if not is_desktop_icons_page():
		return

	create_desktop_icons_from_installed_apps()
	create_desktop_icons_from_workspace()


def import_desktop_icon_fixtures(app: str | None = None, force: bool = False):
	"""Import the icon rows `app` -- or every installed app -- ships in its `desktop_icon/`.

	Carries the same guard as the generator, which is what makes containment total: an
	Apps-mode site holds zero icon rows, generated *or* shipped, so the retiring surface
	cannot contradict the module-first model. Flipping to the grid is what imports them.
	"""
	if not is_desktop_icons_page():
		return

	for app_name in [app] if app else frappe.get_installed_apps():
		for doc_path in get_app_level_files("desktop_icon", app_name):
			if import_file_by_path(doc_path, force=force, ignore_version=True):
				frappe.db.commit(chain=True)  # nosemgrep


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
	"""Give `workspace` an icon on the grid.

	It used to open a `Workspace Sidebar` to hold the link as well. That doctype is now an
	inert archive that the sidebar migration reads as its source, so writing fresh rows to it
	would make the conversion's input a moving target -- and the grid never needed one: the
	icon resolves its route through the module-keyed sidebar payload.
	"""
	new_icon = frappe.new_doc("Desktop Icon")
	new_icon.label = workspace
	new_icon.icon_type = "Link"
	new_icon.link_to = workspace
	new_icon.link_type = "Workspace Sidebar"
	# `ignore_links`: see `create_desktop_icons_from_workspace` -- the sidebar link column is
	# inert, and validating it would look for a document on the archived doctype.
	new_icon.insert(ignore_links=True)
	return {"icon": new_icon.as_dict()}
