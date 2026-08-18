# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

from collections import Counter, defaultdict
from json import loads

import frappe
from frappe import _
from frappe.desk.desk_views import DeskViews
from frappe.desk.desktop import get_workspaces, save_new_widget
from frappe.desk.doctype.desktop_settings.desktop_settings import is_desktop_icons_page
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
		from frappe.types import DF

		charts: DF.Table[WorkspaceChart]
		content: DF.LongText | None
		custom_blocks: DF.Table[WorkspaceCustomBlock]
		external_link: DF.Data | None
		for_user: DF.Data | None
		hide_custom: DF.Check
		icon: DF.Icon | None
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
		# Custom Workspace delta instead, so they survive app updates.
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

		self.validate_duplicate_widget_labels()

	@staticmethod
	def get_widget_label_counts(doc, parentfield) -> Counter:
		"""How many rows of `parentfield` carry each label."""
		rows = doc.get(parentfield) or []
		if parentfield == "links":
			# only `Card Break` rows name a card; the link rows beneath them aren't addressed by label
			rows = [row for row in rows if row.type == "Card Break"]

		counts = Counter()
		for row in rows:
			if label := (row.label or "").strip():
				counts[label] += 1

		return counts

	def validate_duplicate_widget_labels(self):
		"""Widget blocks in `content` reference their child row by label (see `clean_up` in
		frappe/desk/desktop.py), so two widgets of the same type sharing a label collapse into a
		single row on save and one of them silently loses its settings.

		Only duplicates that *this* save introduces are rejected. Ones already stored — shipped app
		data, sites saved before this check existed — are left alone, so an affected workspace
		doesn't become impossible to edit.
		"""
		# app-shipped workspaces are imported verbatim; a duplicate in one is the app's bug to fix
		# and shouldn't take down install/migrate
		if (
			frappe.flags.in_install
			or frappe.flags.in_migrate
			or frappe.flags.in_import
			or frappe.flags.in_patch
		):
			return

		widget_labels = {
			"shortcuts": _("Shortcut"),
			"charts": _("Chart"),
			"quick_lists": _("Quick List"),
			"number_cards": _("Number Card"),
			"custom_blocks": _("Custom Block"),
			"links": _("Card"),
		}

		before_save = self.get_doc_before_save()

		for parentfield, widget_label in widget_labels.items():
			counts = self.get_widget_label_counts(self, parentfield)
			stored = self.get_widget_label_counts(before_save, parentfield) if before_save else {}

			# Compare counts, not just presence: a label already stored twice is grandfathered at
			# two, but a third row under it is a clash *this* save introduces and still has to go.
			duplicates = {
				label for label, count in counts.items() if count > 1 and count > stored.get(label, 0)
			}

			if duplicates:
				frappe.throw(
					_(
						"Duplicate {0} labels: {1}. Labels are used to tell widgets apart when a workspace is saved, so each {0} needs a unique label."
					).format(widget_label, frappe.bold(", ".join(sorted(duplicates)))),
					title=_("Duplicate Label"),
				)

	def before_rename(self, old_name, new_name, merge=False):
		if self.public and not is_workspace_manager() and not disable_saving_as_public():
			frappe.throw(
				_("You need to be {0} to rename this document").format(frappe.bold("Workspace Manager")),
				frappe.PermissionError,
				title=_("Permission Error"),
			)

	def clear_cache(self):
		from frappe.desk.doctype.sidebar.sidebar import clear_computed_base_for

		super().clear_cache()
		# a module with no `Sidebar` has its sidebar computed from workspaces like this one
		clear_computed_base_for(self)
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
		if self.public and not is_workspace_manager():
			frappe.throw(_("You need to be Workspace Manager to delete a public workspace."))

		self.delete_desktop_icon()

	def delete_desktop_icon(self):
		"""Take the workspace's icon off the grid with it.

		Gated on the desktop page by construction rather than left to run in both modes: an
		Apps-mode site holds no icon rows at all, so this used to be harmless only by
		consequence -- the one place containment did not hold by design.

		Matched on the workspace's name, which is what both writers label the icon with
		(autoname is `field:label`). Matching on the title would let a private page take a
		public one's icon down with it, since a private page's name carries an owner suffix
		its title does not.
		"""
		if not is_desktop_icons_page():
			return

		frappe.delete_doc_if_exists("Desktop Icon", self.name)

	def after_delete(self):
		if disable_saving_as_public():
			return

		if self.module and frappe.conf.developer_mode:
			delete_folder(self.module, "Workspace", self.title)

	@staticmethod
	def rename_private_workspaces(old_name, new_name):
		for workspace in frappe.get_all(
			"Workspace",
			filters={"for_user": old_name},
			fields=["name", "title"],
			limit=0,
		):
			new_label = f"{workspace.title}-{new_name}"
			if workspace.name != new_label:
				if frappe.db.exists("Workspace", new_label):
					frappe.db.set_value("Workspace", workspace.name, "for_user", new_name)
					continue
				rename_doc(
					"Workspace",
					workspace.name,
					new_label,
					force=True,
					show_alert=False,
					ignore_permissions=True,
				)
			frappe.db.set_value("Workspace", new_label, {"for_user": new_name, "label": new_label})

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


def workspace_payload(**extra):
	"""The desk state a workspace write invalidates, for the caller to swap into `frappe.boot`.

	`app_data` is in here because the dock is app-scoped: it renders `app_data[app].dock`, so a
	workspace that just gained or changed its module only moves once that mapping is rebuilt.
	Without it the desk needs a full reload to show the change.
	"""
	from frappe.boot import build_entity_module_map, get_app_data, get_module_sidebars

	workspaces = get_workspaces()
	module_sidebars = get_module_sidebars()
	return {
		"workspace_pages": workspaces,
		"app_data": get_app_data([d.name for d in workspaces.get("pages")]),
		# the module-keyed payload, so a hot-swapping caller updates both keyspaces at once
		"module_sidebars": module_sidebars,
		"entity_module": build_entity_module_map(module_sidebars),
		**extra,
	}


def can_edit_workspace(doc):
	"""Whether the session user may change this workspace's settings (including its app mount).

	A Workspace Manager may edit any workspace; anyone may edit their own private one. The desk
	mirrors this predicate to decide whether to offer the "mount to app" action or tell the
	viewer to ask a Workspace Manager, so keep the two in step.
	"""
	return is_workspace_manager() or (not doc.public and doc.for_user == frappe.session.user)


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

	# Sharing a page -- with everyone, or with a group of roles -- is the Workspace Manager's
	# to do; everyone else creates private pages, which is the only level the dialog offers
	# them. Said out loud rather than returning quietly: a caller that asks for a public page
	# and is handed `null` cannot tell the refusal apart from a failure.
	if page.get("public") and not is_workspace_manager():
		frappe.throw(
			_("You need the Workspace Manager role to create a workspace others can see."),
			frappe.PermissionError,
		)
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
	# Every workspace belongs to a module now. The client sends the module whose shell it was
	# created from (`current_module`); fall back to the mounted app's first module so a caller
	# that predates this still works.
	doc.module = page.get("module") or first_module_of_app(page.get("app"))
	doc.type = page.get("type")
	doc.link_to = page.get("link_to")
	doc.link_type = page.get("link_type")
	doc.external_link = page.get("external_link")
	doc.sequence_id = last_sequence_id(doc) + 1
	doc.save(ignore_permissions=True)

	# A workspace no longer owns a sidebar -- its module does. So instead of seeding a
	# self-referencing item on the workspace, add a link to it in the module's sidebar, which
	# is where it will actually be navigated from. A private one is derived rather than
	# written; `add_to_sidebar` is where that branch lives.
	add_to_sidebar(doc)

	return workspace_payload()


def get_workspace_app(doc) -> str | None:
	"""The app a workspace belongs to -- its module's app.

	There is no `Workspace.app` any more. It was a second, hand-set answer to a question the
	module already answers, and the two could disagree.
	"""
	if not doc.module:
		return None
	return frappe.db.get_value("Module Def", doc.module, "app_name")


def first_module_of_app(app: str | None) -> str | None:
	if not app:
		return None
	modules = frappe.get_module_list(app)
	return modules[0] if modules else None


def add_to_sidebar(workspace):
	"""Give a **shared** workspace a way in, from its module's sidebar.

	A link is the whole of it. A workspace used to also be able to *become* the module's home
	page on insert, which was a second, silent way of being reachable; now the module opens on
	the first item of its sidebar, so appearing in that list is the only way in there is, and
	the last one added is correctly not it.

	The link goes in the site's customization layer, never in the sidebar document. The
	document is app content -- on a non-developer-mode site nothing may write to it at all --
	and a workspace somebody created here is site intent. Writing it into the base is what
	would make the base unsafe for an app to overwrite on update.

	**A private workspace gets nothing written for it.** This is the branch D3 asks for: the
	shared branch writes a link, the private branch writes none, because a private page's link
	is derived on read from the workspace itself -- module, owner, title and icon are all
	already on it (`sidebar.get_private_workspaces`). Writing one put a row per private page
	into the document the whole site shares, and every one of those rows was a second copy of
	four columns that could change underneath it.

	Called on every write that can leave a workspace shared, not only on insert, since a page
	that has just been made public needs the link its private form did not store.

	Only reaches modules that *have* a document, which is now the minority: for the rest the
	base is computed, and a public workspace turns up in it on its own because
	`get_module_info` reads them.
	"""
	from frappe.desk.doctype.custom_sidebar.custom_sidebar import (
		add_site_sidebar_item,
	)

	# A Link or a URL workspace is a shortcut to somewhere else, and the sidebar already lists
	# that somewhere else; only a page of its own earns a way in. `type` is empty on pages that
	# predate the field, and those are ordinary workspaces -- the same reading
	# `sidebar.get_private_workspaces` gives them.
	if not workspace.public or (workspace.type and workspace.type != "Workspace"):
		return

	if not workspace.module or not frappe.db.exists("Sidebar", workspace.module):
		return

	sidebar = frappe.get_cached_doc("Sidebar", workspace.module)
	if any(item.link_type == "Workspace" and item.link_to == workspace.name for item in sidebar.items):
		return

	add_site_sidebar_item(
		workspace.module,
		{
			"type": "Link",
			"label": workspace.title,
			"link_type": "Workspace",
			"link_to": workspace.name,
			"icon": workspace.icon,
		},
	)


@frappe.whitelist()
def save_page(name: str, public: str | int, new_widgets: dict, blocks: str):
	public = frappe.parse_json(public)

	doc = frappe.get_doc("Workspace", name)
	can_edit = can_edit_workspace(doc)
	if not can_edit:
		frappe.throw(
			_("You need the Workspace Manager role to edit this workspace."),
			frappe.PermissionError,
		)

	# A standard (app-shipped) workspace is never edited in place on a site -- the site's
	# layout changes are stored as a delta on top of the live base, so app updates keep
	# flowing. In developer mode the app author edits the base itself so it exports to JSON.
	if doc.standard and not frappe.conf.developer_mode:
		from frappe.desk.doctype.custom_workspace.custom_workspace import (
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
		from frappe.desk.doctype.custom_workspace.custom_workspace import (
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

		# A page that has just stopped being private has stopped having a derived link too, so
		# this is where it earns a stored one. Reloaded because the rename above renamed the
		# thing the link has to name.
		add_to_sidebar(frappe.get_doc("Workspace", new_name))

	return {"name": title, "public": public, "label": new_name}


@frappe.whitelist()
def get_manageable_workspaces():
	"""Workspaces the current user may manage in the Manage Workspaces dialog.

	The desk bootinfo only carries the user's *own* private workspaces, so it can't back the
	manager for a Workspace Manager (who should see every workspace, including other users'
	private ones). Everyone else sees only their own private workspaces.
	"""
	# `app` comes along so the dialog can group the workspaces that aren't mounted to any app
	# (and so appear on no dock) into their own list.
	fields = ["name", "title", "icon", "public", "for_user", "standard", "module"]
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
	from frappe.desk.doctype.custom_workspace.custom_workspace import (
		effective_roles,
		get_customization,
	)

	doc = frappe.get_cached_doc("Workspace", name)

	can_edit = can_edit_workspace(doc)
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
		"module": doc.module,
		"app": get_workspace_app(doc),
	}


@frappe.whitelist()
def update_workspace_settings(
	name: str,
	title: str | None = None,
	icon: str | None = None,
	indicator_color: str | None = None,
	access: str | None = None,
	roles: list | str | None = None,
	module: str | None = None,
):
	"""Save appearance + access/roles + module for a workspace from the Manage Workspaces dialog.

	A standard (app-shipped) workspace keeps its app-owned title / route / visibility / module; only
	its appearance and role gating are captured as a Custom Workspace delta. A custom
	(or developer-mode) workspace is edited in place, with `access` mapped onto the underlying
	`public` / `for_user` / `roles` fields (mirroring `new_page`).
	"""
	doc = frappe.get_doc("Workspace", name)

	can_edit = can_edit_workspace(doc)
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
		from frappe.desk.doctype.custom_workspace.custom_workspace import (
			upsert_settings_customization,
		)

		upsert_settings_customization(name, icon=icon, indicator_color=indicator_color, roles=role_names)
		return workspace_payload(name=name)

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
	if module:
		validate_assignable_module(module)
		doc.module = module
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

	# Same as `update_page`: a workspace this save has made shared needs the link its private
	# form derived rather than stored.
	add_to_sidebar(frappe.get_doc("Workspace", new_name))

	return workspace_payload(name=new_name)


@frappe.whitelist()
def delete_page(name: str):
	"""Delete a custom workspace from the Manage Workspaces dialog."""
	doc = frappe.get_doc("Workspace", name)

	if doc.standard and not frappe.conf.developer_mode:
		frappe.throw(_("Standard workspaces cannot be deleted. Reset to standard instead."))

	can_edit = can_edit_workspace(doc)
	if not can_edit:
		frappe.throw(
			_("You need the Workspace Manager role to delete this workspace."),
			frappe.PermissionError,
		)

	frappe.delete_doc("Workspace", name, ignore_permissions=True)
	return workspace_payload()


@frappe.whitelist()
def get_assignable_modules():
	"""Modules a workspace can be assigned to, as `{module, label, app_name, app_title}`.

	Replaces `get_mountable_apps`: a workspace's dock placement follows its module now, so the
	question is which module owns it, not which app it is mounted to.
	"""
	from frappe.utils.modules import is_module_visible

	modules = []
	for row in frappe.get_all("Module Def", fields=["name", "app_name"], order_by="app_name asc, name asc"):
		if not is_module_visible(row.name):
			continue
		# An unplaced module is in no app's dock and has no app to be titled after. Asking
		# `get_hooks` without an app name does not answer "no app" -- it returns the hook merged
		# across every installed one, so every module the site owns came back titled after
		# whichever app happened to be first.
		app_title = (
			(frappe.get_hooks("app_title", app_name=row.app_name) or [row.app_name])[0]
			if row.app_name
			else None
		)
		modules.append(
			{
				"module": row.name,
				"label": row.name,
				"app_name": row.app_name,
				"app_title": app_title,
			}
		)
	return modules


def validate_assignable_module(module: str) -> None:
	"""Refuse a module a workspace may not be filed under.

	Both endpoints that set `Workspace.module` have to make this check, and only one of them
	did. `update_workspace_settings` took a `module` and wrote it straight through, so the same
	operation was validated or not depending on which door it came in by.

	A module that does not exist is already refused -- `Workspace.module` is a Link. What this
	adds is the module the caller cannot *see*: a workspace filed under one is a workspace
	nothing can navigate to, because `get_navigable_modules` drops the module before its
	sidebar is ever built.
	"""
	if module not in {row["module"] for row in get_assignable_modules()}:
		frappe.throw(_("{0} is not a module you can assign a workspace to.").format(frappe.bold(module)))


@frappe.whitelist()
def set_workspace_module(name: str, module: str):
	"""Move a workspace to another module, which is also what moves it between docks."""
	doc = frappe.get_doc("Workspace", name)

	if doc.standard and not frappe.conf.developer_mode:
		# a standard workspace's module is owned by the app that ships it, and Workspace
		# Customization has no field to record a per-site override in
		frappe.throw(_("A standard workspace belongs to the module that ships it."))

	if not can_edit_workspace(doc):
		frappe.throw(
			_("You need the Workspace Manager role to move this workspace."),
			frappe.PermissionError,
		)

	validate_assignable_module(module)

	doc.module = module
	doc.save(ignore_permissions=True)

	return workspace_payload(name=doc.name)


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


def is_workspace_manager(user: str | None = None) -> bool:
	"""Whether `user` may curate navigation for everyone.

	The one definition. The sidebar's layers and the dock's both gate on this, and both used to
	carry a copy of it -- two functions of the same name and the same body, in three files, which
	is three places to change the day the rule changes.

	`Workspace Manager`, not System Manager: the two roles do not imply each other, and the
	holder of the role literally named for curating navigation is the one who should be doing it.
	"""
	return "Workspace Manager" in frappe.get_roles(user)


def check_workspace_manager(message: str) -> None:
	"""Refuse anyone who is not one, with a message saying what they were trying to do."""
	if not is_workspace_manager():
		frappe.throw(message, frappe.PermissionError)
