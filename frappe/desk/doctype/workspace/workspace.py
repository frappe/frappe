# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

from collections import defaultdict
from json import loads

import frappe
from frappe import _
from frappe.desk.desktop import get_workspace_sidebar_items, save_new_widget
from frappe.desk.utils import validate_route_conflict
from frappe.model.document import Document
from frappe.model.rename_doc import rename_doc
from frappe.modules.export_file import delete_folder, export_to_files
from frappe.utils import strip_html


class Workspace(Document):
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
		number_cards: DF.Table[WorkspaceNumberCard]
		parent_page: DF.Link | None
		public: DF.Check
		quick_lists: DF.Table[WorkspaceQuickList]
		restrict_to_domain: DF.Link | None
		roles: DF.Table[HasRole]
		sequence_id: DF.Float
		shortcuts: DF.Table[WorkspaceShortcut]
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

		for d in self.get("links"):
			if d.link_type == "Report" and d.is_query_report != 1:
				d.report_ref_doctype = frappe.get_value("Report", d.link_to, "ref_doctype")

		for shortcut in self.get("shortcuts"):
			if shortcut.type == "Report":
				shortcut.report_ref_doctype = frappe.get_value("Report", shortcut.link_to, "ref_doctype")

		if not self.app and self.module:
			from frappe.modules.utils import get_module_app

			self.app = get_module_app(self.module)

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
			if self.module:
				export_to_files(record_list=[["Workspace", self.name]], record_module=self.module)

			if self.has_value_changed("title") or self.has_value_changed("module"):
				previous = self.get_doc_before_save()
				if previous and previous.get("module") and previous.get("title"):
					delete_folder(previous.get("module"), "Workspace", previous.get("title"))

	def before_export(self, doc):
		if doc.title != doc.label and doc.label == doc.name:
			self.name = doc.name = doc.label = doc.title

	def on_trash(self):
		if self.public and not is_workspace_manager():
			frappe.throw(_("You need to be Workspace Manager to delete a public workspace."))

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
def new_page(new_page):
	if not loads(new_page):
		return

	page = loads(new_page)

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
	doc.indicator_color = page.get("indicator_color")
	doc.content = page.get("content")
	doc.parent_page = page.get("parent_page")
	doc.label = page.get("label")
	doc.for_user = page.get("for_user")
	doc.public = page.get("public")
	doc.app = page.get("app")
	doc.type = page.get("type")
	doc.link_to = page.get("link_to")
	doc.link_type = page.get("link_type")
	doc.external_link = page.get("external_link")
	doc.sequence_id = last_sequence_id(doc) + 1
	doc.save(ignore_permissions=True)

	return get_workspace_sidebar_items()


@frappe.whitelist()
def save_page(name, public, new_widgets, blocks):
	public = frappe.parse_json(public)

	doc = frappe.get_doc("Workspace", name)
	if not doc.type:
		doc.type = "Workspace"

	doc.content = blocks

	save_new_widget(doc, name, blocks, new_widgets)

	return {"name": name, "public": public, "label": doc.label}


@frappe.whitelist()
def update_page(name, title, icon, indicator_color, parent, public):
	public = frappe.parse_json(public)
	doc = frappe.get_doc("Workspace", name)

	if not doc.get("public") and doc.get("for_user") != frappe.session.user and not is_workspace_manager():
		frappe.throw(
			_("Need Workspace Manager role to edit private workspace of other users"),
			frappe.PermissionError,
		)

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
