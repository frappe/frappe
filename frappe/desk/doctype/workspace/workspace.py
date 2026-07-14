# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

from collections import defaultdict
from json import loads

import frappe
from frappe import _
from frappe.boot import get_sidebar_items
from frappe.desk.desk_views import DeskViews
from frappe.desk.desktop import get_workspaces, save_new_widget
from frappe.desk.utils import validate_route_conflict
from frappe.model.document import Document
from frappe.model.rename_doc import rename_doc
from frappe.modules.export_file import delete_folder, export_to_files
from frappe.utils import strip_html


class Workspace(Document, DeskViews):
	_DOCTYPE_NAME = "Workspace"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.has_role.has_role import HasRole
		from frappe.desk.doctype.workspace_chart.workspace_chart import WorkspaceChart
		from frappe.desk.doctype.workspace_custom_block.workspace_custom_block import WorkspaceCustomBlock
		from frappe.desk.doctype.workspace_link.workspace_link import WorkspaceLink
		from frappe.desk.doctype.workspace_number_card.workspace_number_card import WorkspaceNumberCard
		from frappe.desk.doctype.workspace_quick_list.workspace_quick_list import WorkspaceQuickList
		from frappe.desk.doctype.workspace_shortcut.workspace_shortcut import WorkspaceShortcut
		from frappe.desk.doctype.workspace_sidebar_item.workspace_sidebar_item import WorkspaceSidebarItem
		from frappe.types import DF

		app: DF.Data | None
		charts: DF.Table[WorkspaceChart]
		content: DF.LongText | None
		custom_blocks: DF.Table[WorkspaceCustomBlock]
		external_link: DF.Data | None
		for_user: DF.Data | None
		hide_custom: DF.Check
		indicator_color: DF.Literal[
			"green",
			"cyan",
			"blue",
			"orange",
			"yellow",
			"gray",
			"grey",
			"red",
			"pink",
			"darkgrey",
			"purple",
			"light-blue",
		]
		is_hidden: DF.Check
		label: DF.Data
		link_to: DF.DynamicLink | None
		link_type: DF.Literal["DocType", "Page", "Report"]
		links: DF.Table[WorkspaceLink]
		module: DF.Link | None
		module_onboarding: DF.Link | None
		number_cards: DF.Table[WorkspaceNumberCard]
		parent_page: DF.Link | None
		public: DF.Check
		quick_lists: DF.Table[WorkspaceQuickList]
		restrict_to_domain: DF.Link | None
		roles: DF.Table[HasRole]
		sequence_id: DF.Float
		shortcuts: DF.Table[WorkspaceShortcut]
		sidebar_items: DF.Table[WorkspaceSidebarItem]
		standard: DF.Check
		title: DF.Data
		type: DF.Literal["Workspace", "Link", "URL"]
	# end: auto-generated types

	def validate(self):
		self.title = strip_html(self.title)

		if self.public and not is_workspace_manager() and not disable_saving_as_public():
			frappe.throw(_("You need to be Workspace Manager to edit this document"))
		if self.has_value_changed("title"):
			validate_route_conflict(self.doctype, self.title)
		else:
			validate_route_conflict(self.doctype, self.name)

		try:
			if not isinstance(loads(self.content), list):
				raise
		except Exception:
			frappe.throw(_("Content data shoud be a list"))

		# Keep standard (app-shipped) workspaces app-owned: their content is only changed by
		# import (migrate/install) or by an app author in developer mode. Site edits go to a
		# Workspace Customization delta instead, so they survive app updates.
		if (
			self.standard
			and not self.is_new()
			and self.has_value_changed("content")
			and not frappe.conf.developer_mode
			and not disable_saving_as_public()
		):
			frappe.throw(
				_("Standard workspaces can't be edited directly. Your changes are saved as a customization.")
			)

		for d in self.get("links"):
			if d.link_type == "Report" and d.is_query_report != 1:
				d.report_ref_doctype = frappe.get_value("Report", d.link_to, "ref_doctype")

		for shortcut in self.get("shortcuts"):
			if shortcut.type == "Report":
				shortcut.report_ref_doctype = frappe.get_value("Report", shortcut.link_to, "ref_doctype")

		if self.standard:
			if not self.app and self.module:
				from frappe.modules.utils import get_module_app

				self.app = get_module_app(self.module)

	def before_rename(self, old_name, new_name, merge=False):
		if self.public and not is_workspace_manager() and not disable_saving_as_public():
			frappe.throw(
				_("You need to be {0} to rename this document").format(frappe.bold("Workspace Manager")),
				frappe.PermissionError,
				title=_("Permission Error"),
			)

	def clear_cache(self):
		super().clear_cache()
		if self.for_user:
			frappe.cache.hdel("bootinfo", self.for_user)
		else:
			frappe.cache.delete_key("bootinfo")

	def on_update(self):
		if disable_saving_as_public():
			return

		if frappe.conf.developer_mode and self.public:
			self.export_workspace()

			if self.has_value_changed("title") or self.has_value_changed("module"):
				previous = self.get_doc_before_save()
				if previous and previous.get("module") and previous.get("title"):
					delete_folder(previous.get("module"), "Workspace", previous.get("title"))

	def export_workspace(self):
		"""Export a standard workspace to its module's files (developer mode only)."""
		# `self.module` guards the export: it drives the on-disk path (`get_module_path`), so a
		# standard workspace with no module would crash inside `export_to_files`.
		if frappe.conf.developer_mode and self.standard and self.module:
			export_to_files(record_list=[["Workspace", self.name]], record_module=self.module)

	def before_export(self, doc):
		if doc.title != doc.label and doc.label == doc.name:
			self.name = doc.name = doc.label = doc.title

	def on_trash(self):
		if not self.module:
			self.delete_sidebar()
			self.delete_desktop_icon()
		if self.public and not is_workspace_manager():
			frappe.throw(_("You need to be Workspace Manager to delete a public workspace."))

	def delete_desktop_icon(self):
		frappe.delete_doc_if_exists("Desktop Icon", self.title)

	def delete_sidebar(self):
		frappe.delete_doc_if_exists("Workspace Sidebar", self.title)

	def after_delete(self):
		if disable_saving_as_public():
			return

		if self.module and frappe.conf.developer_mode:
			delete_folder(self.module, "Workspace", self.title)

	@staticmethod
	def get_module_wise_workspaces():
		workspaces = frappe.get_all(
			"Workspace",
			fields=["name", "module"],
			filters={"for_user": "", "public": 1},
			order_by="creation",
		)

		module_workspaces = defaultdict(list)

		for workspace in workspaces:
			if not workspace.module:
				continue
			module_workspaces[workspace.module].append(workspace.name)

		return module_workspaces

	def get_link_groups(self):
		cards = []
		current_card = frappe._dict(
			{
				"label": "Link",
				"type": "Card Break",
				"icon": None,
				"hidden": False,
			}
		)

		card_links = []

		for link in self.links:
			link = link.as_dict()
			if link.type == "Card Break":
				if card_links and (
					not current_card.get("only_for")
					or current_card.get("only_for") == frappe.get_system_settings("country")
				):
					current_card["links"] = card_links
					cards.append(current_card)

				current_card = link
				card_links = []
			elif not link.get("only_for") or link.get("only_for") == frappe.get_system_settings("country"):
				card_links.append(link)

		current_card["links"] = card_links
		cards.append(current_card)

		return cards

	def build_links_table_from_card(self, config):
		for idx, card in enumerate(config):
			links = loads(card.get("links"))

			# remove duplicate before adding
			for idx, link in enumerate(self.links):
				if link.get("label") == card.get("label") and link.get("type") == "Card Break":
					# count and set number of links for the card if link_count is 0
					if link.link_count == 0:
						for count, card_link in enumerate(self.links[idx + 1 :]):
							if card_link.get("type") == "Card Break":
								break
							link.link_count = count + 1

					del self.links[idx : idx + link.link_count + 1]

			self.append(
				"links",
				{
					"label": card.get("label"),
					"type": "Card Break",
					"icon": card.get("icon"),
					"description": card.get("description"),
					"hidden": card.get("hidden") or False,
					"link_count": card.get("link_count"),
					"idx": 1 if not self.links else self.links[-1].idx + 1,
				},
			)

			for link in links:
				self.append(
					"links",
					{
						"label": link.get("label"),
						"type": "Link",
						"link_type": link.get("link_type"),
						"link_to": link.get("link_to"),
						"onboard": link.get("onboard"),
						"only_for": link.get("only_for"),
						"dependencies": link.get("dependencies"),
						"is_query_report": link.get("is_query_report"),
						"idx": self.links[-1].idx + 1,
					},
				)


def disable_saving_as_public():
	return (
		frappe.flags.in_install
		or frappe.flags.in_uninstall
		or frappe.flags.in_patch
		or frappe.in_test
		or frappe.flags.in_fixtures
		or frappe.flags.in_migrate
	)


def get_link_type(key):
	key = key.lower()

	link_type_map = {"doctype": "DocType", "page": "Page", "report": "Report"}

	if key in link_type_map:
		return link_type_map[key]

	return "DocType"


def get_report_type(report):
	report_type = frappe.get_value("Report", report, "report_type")
	return report_type in ["Query Report", "Script Report", "Custom Report"]


@frappe.whitelist()
def new_page(new_page: dict):
	# frappe auto-parses JSON-looking string args back into objects before this runs, so
	# `new_page` may already be a dict; only `loads` it when it's still a string.
	page = frappe.parse_json(new_page)
	if not page:
		return

	if page.get("public") and not is_workspace_manager():
		return
	elif (
		not page.get("public") and page.get("for_user") != frappe.session.user and not is_workspace_manager()
	):
		frappe.throw(_("Cannot create private workspace of other users"), frappe.PermissionError)

	elif not frappe.has_permission(doctype="Workspace", ptype="create"):
		frappe.flags.error_message = _("User {0} does not have the permission to create a Workspace.").format(
			frappe.bold(frappe.session.user)
		)
		raise frappe.PermissionError

	doc = frappe.new_doc("Workspace")
	doc.title = page.get("title")
	doc.icon = page.get("icon") or "grid"
	doc.content = page.get("content")
	doc.parent_page = page.get("parent_page")
	doc.label = page.get("label")
	doc.for_user = page.get("for_user")
	doc.public = page.get("public")
	for role in page.get("roles") or []:
		if role.get("role"):
			doc.append("roles", {"role": role.get("role")})
	doc.app = page.get("app")
	doc.type = page.get("type")
	doc.link_to = page.get("link_to")
	doc.link_type = page.get("link_type")
	doc.external_link = page.get("external_link")
	doc.sequence_id = last_sequence_id(doc) + 1
	doc.save(ignore_permissions=True)

	# Seed a new workspace's sidebar with a link to itself, so landing on its shell shows the
	# workspace in its own sidebar instead of an empty "No Sidebar Items" state. This is done
	# after the initial save: the self-link's `link_to` is validated against the Workspace
	# doctype, so the workspace row must already exist.
	if doc.type == "Workspace":
		doc.append(
			"sidebar_items",
			{
				"type": "Link",
				"label": doc.title,
				"link_type": "Workspace",
				"link_to": doc.name,
				"icon": doc.icon,
			},
		)
		doc.save(ignore_permissions=True)

	workspaces = get_workspaces()
	return {"workspace_pages": workspaces, "sidebar_items": get_sidebar_items()}


@frappe.whitelist()
def save_page(name: str, public: str | int, new_widgets: dict, blocks: str):
	public = frappe.parse_json(public)

	doc = frappe.get_doc("Workspace", name)
	can_edit = is_workspace_manager() or (not doc.public and doc.for_user == frappe.session.user)
	if not can_edit:
		frappe.throw(
			_("You need the Workspace Manager role to edit this workspace."),
			frappe.PermissionError,
		)

	# A standard (app-shipped) workspace is never edited in place on a site -- the site's
	# layout changes are stored as a delta on top of the live base, so app updates keep
	# flowing. In developer mode the app author edits the base itself so it exports to JSON.
	if doc.standard and not frappe.conf.developer_mode:
		from frappe.desk.doctype.workspace_customization.workspace_customization import (
			upsert_content_customization,
		)

		upsert_content_customization(name, frappe.parse_json(blocks), frappe.parse_json(new_widgets or "{}"))
		return {"name": name, "public": public, "label": doc.label}

	if not doc.type:
		doc.type = "Workspace"

	doc.content = blocks

	save_new_widget(doc, name, blocks, new_widgets)

	return {"name": name, "public": public, "label": doc.label}


@frappe.whitelist()
def update_page(name: str, title: str, icon: str, indicator_color: str, parent: str, public: str | int):
	public = frappe.parse_json(public)
	doc = frappe.get_doc("Workspace", name)

	if doc.get("public") and not is_workspace_manager():
		frappe.throw(_("Need Workspace Manager role to edit public workspaces."))
	elif not doc.get("public") and doc.get("for_user") != frappe.session.user and not is_workspace_manager():
		frappe.throw(
			_("Need Workspace Manager role to edit private workspace of other users."),
			frappe.PermissionError,
		)

	# A standard workspace keeps its app-owned title/route; on a site only the appearance
	# overrides (icon / colour) are captured as a delta. In developer mode the app author
	# edits the base itself so it exports to JSON.
	if doc.standard and not frappe.conf.developer_mode:
		from frappe.desk.doctype.workspace_customization.workspace_customization import (
			upsert_property_customization,
		)

		upsert_property_customization(name, icon=icon, indicator_color=indicator_color)
		return {"name": doc.title, "public": doc.public, "label": doc.label}

	if doc:
		child_docs = frappe.get_all("Workspace", filters={"parent_page": doc.title, "public": doc.public})
		doc.title = title
		doc.icon = icon
		doc.indicator_color = indicator_color
		doc.parent_page = parent
		if doc.public != public:
			doc.sequence_id = frappe.db.count("Workspace", {"public": public}, cache=True)
			doc.public = public
		doc.for_user = "" if public else doc.for_user or frappe.session.user
		doc.label = new_name = f"{title}-{doc.for_user}" if doc.for_user else title
		doc.save(ignore_permissions=True)

		if name != new_name:
			rename_doc("Workspace", name, new_name, force=True, ignore_permissions=True)

		# update new name and public in child pages
		if child_docs:
			for child in child_docs:
				child_doc = frappe.get_doc("Workspace", child.name)
				child_doc.parent_page = doc.title
				if child_doc.public != public:
					child_doc.public = public
				child_doc.for_user = "" if public else child_doc.for_user or frappe.session.user
				child_doc.label = new_child_name = (
					f"{child_doc.title}-{child_doc.for_user}" if child_doc.for_user else child_doc.title
				)
				child_doc.save(ignore_permissions=True)

				if child.name != new_child_name:
					rename_doc("Workspace", child.name, new_child_name, force=True, ignore_permissions=True)

	return {"name": title, "public": public, "label": new_name}


@frappe.whitelist()
def get_manageable_workspaces():
	"""Workspaces the current user may manage in the Manage Workspaces dialog.

	The desk bootinfo only carries the user's *own* private workspaces, so it can't back the
	manager for a Workspace Manager (who should see every workspace, including other users'
	private ones). Everyone else sees only their own private workspaces.
	"""
	fields = ["name", "title", "icon", "public", "for_user", "standard"]
	if is_workspace_manager():
		filters = {}
	else:
		filters = {"public": 0, "for_user": frappe.session.user}
	return frappe.get_all(
		"Workspace",
		fields=fields,
		filters=filters,
		order_by="public desc, sequence_id asc",
		ignore_permissions=True,
	)


@frappe.whitelist()
def get_workspace_settings(name: str):
	"""Effective, editable metadata for the Manage Workspaces dialog.

	Resolves the site's customization delta for a standard (app-shipped) workspace so the
	dialog shows a single truth (base + overrides), matching what the desk renders.
	"""
	from frappe.desk.doctype.workspace_customization.workspace_customization import (
		effective_roles,
		get_customization,
	)

	doc = frappe.get_cached_doc("Workspace", name)

	can_edit = is_workspace_manager() or (not doc.public and doc.for_user == frappe.session.user)
	if not can_edit:
		frappe.throw(
			_("You need the Workspace Manager role to manage this workspace."),
			frappe.PermissionError,
		)

	is_standard = bool(doc.standard) and not frappe.conf.developer_mode

	roles = [r.role for r in doc.roles]
	icon = doc.icon
	indicator_color = doc.indicator_color

	if is_standard and (customization := get_customization(name)):
		roles = effective_roles([r.role for r in doc.roles], customization)
		icon = customization.icon or icon
		indicator_color = customization.indicator_color or indicator_color

	if not doc.public:
		access = "private"
	elif roles:
		access = "group"
	else:
		access = "public"

	return {
		"name": doc.name,
		"title": doc.title,
		"icon": icon,
		"indicator_color": indicator_color,
		"public": doc.public,
		"for_user": doc.for_user,
		"standard": is_standard,
		"access": access,
		"roles": sorted(roles),
	}


@frappe.whitelist()
def update_workspace_settings(
	name: str,
	title: str | None = None,
	icon: str | None = None,
	indicator_color: str | None = None,
	access: str | None = None,
	roles: list | str | None = None,
):
	"""Save appearance + access/roles for a workspace from the Manage Workspaces dialog.

	A standard (app-shipped) workspace keeps its app-owned title / route / visibility; only
	its appearance and role gating are captured as a Workspace Customization delta. A custom
	(or developer-mode) workspace is edited in place, with `access` mapped onto the underlying
	`public` / `for_user` / `roles` fields (mirroring `new_page`).
	"""
	doc = frappe.get_doc("Workspace", name)

	can_edit = is_workspace_manager() or (not doc.public and doc.for_user == frappe.session.user)
	if not can_edit:
		frappe.throw(
			_("You need the Workspace Manager role to edit this workspace."),
			frappe.PermissionError,
		)

	role_list = frappe.parse_json(roles) if isinstance(roles, str) else (roles or [])
	# a row may be a `{role: ...}` dict (from the dialog grid) or a bare role name
	role_names = sorted({(r.get("role") if isinstance(r, dict) else r) for r in role_list if r})
	# roles only gate access when the workspace is shared with a group
	if access != "group":
		role_names = []

	is_standard = bool(doc.standard) and not frappe.conf.developer_mode
	if is_standard:
		from frappe.desk.doctype.workspace_customization.workspace_customization import (
			upsert_settings_customization,
		)

		upsert_settings_customization(name, icon=icon, indicator_color=indicator_color, roles=role_names)
		return {"workspace_pages": get_workspaces(), "sidebar_items": get_sidebar_items(), "name": name}

	# custom workspace: edit in place, mapping the access choice onto public / for_user / roles
	make_public = 0 if access == "private" else 1
	if make_public and not is_workspace_manager():
		frappe.throw(
			_("You need the Workspace Manager role to make a workspace public."),
			frappe.PermissionError,
		)

	child_docs = frappe.get_all("Workspace", filters={"parent_page": doc.title, "public": doc.public})

	if title:
		doc.title = strip_html(title)
	if icon:
		doc.icon = icon
	if indicator_color is not None:
		doc.indicator_color = indicator_color
	doc.set("roles", [{"role": r} for r in role_names])
	if doc.public != make_public:
		doc.sequence_id = frappe.db.count("Workspace", {"public": make_public}, cache=True)
		doc.public = make_public
	doc.for_user = "" if make_public else doc.for_user or frappe.session.user
	doc.label = new_name = f"{doc.title}-{doc.for_user}" if doc.for_user else doc.title
	doc.save(ignore_permissions=True)

	if name != new_name:
		rename_doc("Workspace", name, new_name, force=True, ignore_permissions=True)

	# propagate the (possibly renamed / re-scoped) parent to its child pages, as `update_page` does
	for child in child_docs:
		child_doc = frappe.get_doc("Workspace", child.name)
		child_doc.parent_page = doc.title
		if child_doc.public != make_public:
			child_doc.public = make_public
		child_doc.for_user = "" if make_public else child_doc.for_user or frappe.session.user
		child_doc.label = new_child_name = (
			f"{child_doc.title}-{child_doc.for_user}" if child_doc.for_user else child_doc.title
		)
		child_doc.save(ignore_permissions=True)
		if child.name != new_child_name:
			rename_doc("Workspace", child.name, new_child_name, force=True, ignore_permissions=True)

	return {"workspace_pages": get_workspaces(), "sidebar_items": get_sidebar_items(), "name": new_name}


@frappe.whitelist()
def delete_page(name: str):
	"""Delete a custom workspace from the Manage Workspaces dialog."""
	doc = frappe.get_doc("Workspace", name)

	if doc.standard and not frappe.conf.developer_mode:
		frappe.throw(_("Standard workspaces cannot be deleted. Reset to standard instead."))

	can_edit = is_workspace_manager() or (not doc.public and doc.for_user == frappe.session.user)
	if not can_edit:
		frappe.throw(
			_("You need the Workspace Manager role to delete this workspace."),
			frappe.PermissionError,
		)

	frappe.delete_doc("Workspace", name, ignore_permissions=True)
	return {"workspace_pages": get_workspaces(), "sidebar_items": get_sidebar_items()}


def last_sequence_id(doc):
	doc_exists = frappe.db.exists({"doctype": "Workspace", "public": doc.public, "for_user": doc.for_user})

	if not doc_exists:
		return 0

	return frappe.get_all(
		"Workspace",
		fields=["sequence_id"],
		filters={"public": doc.public, "for_user": doc.for_user},
		order_by="sequence_id desc",
	)[0].sequence_id


def get_page_list(fields, filters):
	return frappe.get_all("Workspace", fields=fields, filters=filters, order_by="sequence_id asc")


def is_workspace_manager():
	return "Workspace Manager" in frappe.get_roles()
