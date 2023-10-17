# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

from collections import defaultdict
from json import loads

import frappe
from frappe import _
from frappe.desk.desktop import save_new_widget
from frappe.desk.utils import validate_route_conflict
from frappe.model.document import Document
from frappe.model.rename_doc import rename_doc
from frappe.modules.export_file import delete_folder, export_to_files


class Workspace(Document):
	def validate(self):
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

	def clear_cache(self):
		super().clear_cache()
		if self.for_user:
			frappe.cache().hdel("bootinfo", self.for_user)
		else:
			frappe.cache().delete_key("bootinfo")

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
			else:
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
		or frappe.flags.in_test
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
		not page.get("public")
		and page.get("for_user") != frappe.session.user
		and not is_workspace_manager()
	):
		frappe.throw(_("Cannot create private workspace of other users"), frappe.PermissionError)

	doc = frappe.new_doc("Workspace")
	doc.title = page.get("title")
	doc.icon = page.get("icon")
	doc.content = page.get("content")
	doc.parent_page = page.get("parent_page")
	doc.label = page.get("label")
	doc.for_user = page.get("for_user")
	doc.public = page.get("public")
	doc.sequence_id = last_sequence_id(doc) + 1
	doc.save(ignore_permissions=True)

	return doc


@frappe.whitelist()
def save_page(title, public, new_widgets, blocks):
	public = frappe.parse_json(public)

	filters = {"public": public, "label": title}

	if not public:
		filters = {"for_user": frappe.session.user, "label": title + "-" + frappe.session.user}
	pages = frappe.get_all("Workspace", filters=filters)
	if pages:
		doc = frappe.get_doc("Workspace", pages[0])

	doc.content = blocks
	doc.save(ignore_permissions=True)

	save_new_widget(doc, title, blocks, new_widgets)

	return {"name": title, "public": public, "label": doc.label}


@frappe.whitelist()
def update_page(name, title, icon, parent, public):
	public = frappe.parse_json(public)
	doc = frappe.get_doc("Workspace", name)

	if (
		not doc.get("public")
		and doc.get("for_user") != frappe.session.user
		and not is_workspace_manager()
	):
		frappe.throw(
			_("Need Workspace Manager role to edit private workspace of other users"),
			frappe.PermissionError,
		)

	if doc:
		doc.title = title
		doc.icon = icon
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
		child_docs = frappe.get_all(
			"Workspace", filters={"parent_page": doc.title, "public": doc.public}
		)
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


def hide_unhide_page(page_name: str, is_hidden: bool):
	page = frappe.get_doc("Workspace", page_name)

	if page.get("public") and not is_workspace_manager():
		frappe.throw(
			_("Need Workspace Manager role to hide/unhide public workspaces"), frappe.PermissionError
		)

	if (
		not page.get("public")
		and page.get("for_user") != frappe.session.user
		and not is_workspace_manager()
	):
		frappe.throw(_("Cannot update private workspace of other users"), frappe.PermissionError)

	page.is_hidden = int(is_hidden)
	page.save(ignore_permissions=True)
	return True


@frappe.whitelist()
def hide_page(page_name: str):
	return hide_unhide_page(page_name, 1)


@frappe.whitelist()
def unhide_page(page_name: str):
	return hide_unhide_page(page_name, 0)


@frappe.whitelist()
def duplicate_page(page_name, new_page):
	if not loads(new_page):
		return

	new_page = loads(new_page)

	if new_page.get("is_public") and not is_workspace_manager():
		return

	old_doc = frappe.get_doc("Workspace", page_name)
	doc = frappe.copy_doc(old_doc)
	doc.title = new_page.get("title")
	doc.icon = new_page.get("icon")
	doc.parent_page = new_page.get("parent") or ""
	doc.public = new_page.get("is_public")
	doc.for_user = ""
	doc.label = doc.title
	doc.module = ""
	if not doc.public:
		doc.for_user = doc.for_user or frappe.session.user
		doc.label = f"{doc.title}-{doc.for_user}"
	doc.name = doc.label
	if old_doc.public == doc.public:
		doc.sequence_id += 0.1
	else:
		doc.sequence_id = last_sequence_id(doc) + 1
	doc.insert(ignore_permissions=True)

	return doc


@frappe.whitelist()
def delete_page(page):
	if not loads(page):
		return

	page = loads(page)

	if page.get("public") and not is_workspace_manager():
		frappe.throw(
			_("Cannot delete public workspace without Workspace Manager role"),
			frappe.PermissionError,
		)
	elif not page.get("public") and not is_workspace_manager():
		workspace_owner = frappe.get_value("Workspace", page.get("name"), "for_user")
		if workspace_owner != frappe.session.user:
			frappe.throw(
				_("Cannot delete private workspace of other users"),
				frappe.PermissionError,
			)

	if frappe.db.exists("Workspace", page.get("name")):
		frappe.get_doc("Workspace", page.get("name")).delete(ignore_permissions=True)

	return {"name": page.get("name"), "public": page.get("public"), "title": page.get("title")}


@frappe.whitelist()
def sort_pages(sb_public_items, sb_private_items):
	if not loads(sb_public_items) and not loads(sb_private_items):
		return

	sb_public_items = loads(sb_public_items)
	sb_private_items = loads(sb_private_items)

	workspace_public_pages = get_page_list(["name", "title"], {"public": 1})
	workspace_private_pages = get_page_list(["name", "title"], {"for_user": frappe.session.user})

	if sb_private_items:
		return sort_page(workspace_private_pages, sb_private_items)

	if sb_public_items and is_workspace_manager():
		return sort_page(workspace_public_pages, sb_public_items)

	return False


def sort_page(workspace_pages, pages):
	for seq, d in enumerate(pages):
		for page in workspace_pages:
			if page.title == d.get("title"):
				doc = frappe.get_doc("Workspace", page.name)
				doc.sequence_id = seq + 1
				doc.parent_page = d.get("parent_page") or ""
				doc.flags.ignore_links = True
				doc.save(ignore_permissions=True)
				break

	return True


def last_sequence_id(doc):
	doc_exists = frappe.db.exists(
		{"doctype": "Workspace", "public": doc.public, "for_user": doc.for_user}
	)

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
