# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.modules.export_file import delete_folder, export_to_files


class ModuleSidebar(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.module_sidebar_item.module_sidebar_item import ModuleSidebarItem
		from frappe.desk.doctype.module_sidebar_workspace.module_sidebar_workspace import (
			ModuleSidebarWorkspace,
		)
		from frappe.types import DF

		custom: DF.Check
		for_user: DF.Link | None
		items: DF.Table[ModuleSidebarItem]
		module: DF.Link
		workspaces: DF.Table[ModuleSidebarWorkspace]
	# end: auto-generated types

	def autoname(self):
		if frappe.conf.developer_mode:
			self.name = self.module
		else:
			self.name = f"{self.module}-{self.for_user}"

	def on_update(self):
		if frappe.conf.developer_mode and not self.custom:
			export_to_files(record_list=[["Module Sidebar", self.name]], record_module=self.module)

			if self.has_value_changed("module"):
				previous = self.get_doc_before_save()
				if previous and previous.get("module") and previous.get("label"):
					delete_folder(previous.get("module"), "Module Sidebar", previous.get("label"))

	def after_delete(self):
		if frappe.conf.developer_mode and self.module and not self.custom:
			delete_folder(self.module, "Module Sidebar", self.label)


@frappe.whitelist()
def get_module_sidebar(module: str) -> dict:
	"""Returns user specfic/global sidebar for a module"""
	sidebar = frappe.db.exists("Module Sidebar", {"module": module, "for_user": frappe.session.user})
	if not sidebar:
		sidebar = frappe.db.exists("Module Sidebar", {"module": module, "for_user": ("is", "Not Set")})

	doc = frappe.get_cached_doc("Module Sidebar", sidebar)
	sections = []
	current_section = None
	# first link in the sidebar
	module_home = None

	if doc.workspaces:
		module_home = frappe._dict(
			{
				"workspace": doc.workspaces[0].workspace,
			}
		)

	for item in doc.items:
		item = item.as_dict()
		if item.type == "Spacer":
			sections.append(item)
			current_section = None
		elif item.type == "Section Break":
			current_section = frappe._dict(item)
			current_section["links"] = []
			sections.append(current_section)
		elif item.type == "Link":
			if current_section:
				current_section["links"].append(item)
			else:
				sections.append(item)

			if not module_home:
				module_home = item

	return frappe._dict(
		{
			"workspaces": doc.workspaces,
			"sections": sections,
			"module": module,
			"module_home": module_home,
			"name": doc.name,
		}
	)


@frappe.whitelist()
def save_module_sidebar(name: str, workspaces: list[dict], sections: list[dict]) -> None:
	"""Update module sidebar"""

	def get_sidebar_doc():
		doc = frappe.get_doc("Module Sidebar", name)

		if not frappe.conf.developer_mode:
			# create a new sidebar for the user
			sidebar = frappe.new_doc("Module Sidebar")
			sidebar.module = doc.module
			sidebar.for_user = frappe.session.user
			sidebar.custom = 1
			return sidebar
		return doc

	def append_item(item):
		doc.append(
			"items",
			{
				"type": item.get("type"),
				"label": item.get("label"),
				"icon": item.get("icon"),
				"link_type": item.get("link_type"),
				"link_to": item.get("link_to"),
			},
		)

	doc = get_sidebar_doc()
	doc.workspaces = []
	doc.items = []

	for workspace in workspaces:
		doc.append(
			"workspaces",
			{
				"workspace": workspace.get("workspace"),
				"icon": workspace.get("icon"),
				"label": workspace.get("label"),
			},
		)

	for section in sections:
		if section.get("type") in ["Link", "Spacer"]:
			append_item(section)

		elif section.get("type") == "Section Break":
			doc.append(
				"items",
				{
					"type": "Section Break",
					"label": section.get("label"),
				},
			)
			for item in section.get("links"):
				append_item(item)

	doc.save()
