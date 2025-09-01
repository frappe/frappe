# Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt
import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists

from studio.export import can_export, delete_file, remove_null_fields, write_document_file
from studio.utils import camel_case_to_kebab_case


class StudioPage(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from studio.studio.doctype.studio_page_client_script.studio_page_client_script import (
			StudioPageClientScript,
		)
		from studio.studio.doctype.studio_page_resource.studio_page_resource import StudioPageResource
		from studio.studio.doctype.studio_page_variable.studio_page_variable import StudioPageVariable
		from studio.studio.doctype.studio_page_watcher.studio_page_watcher import StudioPageWatcher

		blocks: DF.JSON | None
		client_scripts: DF.TableMultiSelect[StudioPageClientScript]
		draft_blocks: DF.JSON | None
		frappe_app: DF.Literal[None]
		is_standard: DF.Check
		page_name: DF.Data | None
		page_title: DF.Data | None
		published: DF.Check
		resources: DF.Table[StudioPageResource]
		route: DF.Data | None
		studio_app: DF.Link | None
		variables: DF.Table[StudioPageVariable]
		watchers: DF.Table[StudioPageWatcher]
	# end: auto-generated types

	def autoname(self):
		if not self.name:
			self.name = f"page-{frappe.generate_hash(length=8)}"

	def before_insert(self):
		if isinstance(self.blocks, list):
			self.blocks = frappe.as_json(self.blocks, indent=None)
		if isinstance(self.draft_blocks, list):
			self.draft_blocks = frappe.as_json(self.draft_blocks, indent=None)
		if not self.blocks:
			self.blocks = "[]"
		if not self.page_title:
			self.page_title = "My Page"
			self.page_title = append_number_if_name_exists(
				"Studio Page",
				self.page_title,
				fieldname="page_title",
				filters={
					"studio_app": self.studio_app,
				},
			)
		if not self.route:
			self.route = f"{camel_case_to_kebab_case(self.page_title, True)}-{frappe.generate_hash(length=4)}"

	def after_insert(self):
		app_home = frappe.db.get_value("Studio App", self.studio_app, "app_home")
		if not app_home:
			frappe.db.set_value("Studio App", self.studio_app, "app_home", self.name)

	def before_validate(self):
		# vue router needs a leading slash
		if not self.route.startswith("/"):
			self.route = f"/{self.route}"

	def validate(self):
		if hasattr(self, "_skip_validate"):
			# passed from the frontend for faster page saves when variables & resources are not changed
			return

		self.validate_variables()
		self.process_resources()

	def on_update(self):
		self.export_page()

	def export_page(self):
		if can_export(self):
			write_document_file(self, folder=self.get_folder_path())
			self.delete_old_page_file()
			self.export_components()

	def delete_old_page_file(self):
		if self.has_value_changed("page_title"):
			doc_before_save = self.get_doc_before_save()
			if doc_before_save:
				delete_file(self.get_folder_path(), f"{frappe.scrub(doc_before_save.page_title)}.json")

	def export_components(self):
		if components := self.get_studio_components():
			folder = self.get_component_folder_path()
			frappe.create_folder(folder, with_init=True)
			for component in components:
				doc = frappe.get_doc("Studio Component", component)
				write_document_file(doc, folder=folder)

	def get_studio_components(self):
		components = set()

		def add_component(block):
			if block.get("isStudioComponent"):
				components.add(block.get("componentName"))

			for child in block.get("children", []):
				add_component(child)

			if slots := block.get("componentSlots"):
				for slot in slots.values():
					if isinstance(slot.get("slotContent"), str):
						continue
					for slot_child in slot.get("slotContent"):
						add_component(slot_child)

		def get_root_block(blocks):
			if isinstance(blocks, str):
				blocks = frappe.parse_json(blocks)
			return blocks[0]

		if self.blocks:
			root_block = get_root_block(self.blocks)
			add_component(root_block)
		if self.draft_blocks:
			root_block = get_root_block(self.draft_blocks)
			add_component(root_block)

		return components

	def on_trash(self):
		if can_export(self):
			path = self.get_folder_path(with_filename=True)
			delete_file(path)

	def validate_variables(self):
		# check for duplicate variable names and show the duplicate variable name
		variable_names = [variable.variable_name for variable in self.variables]
		duplicate_variable_names = set(x for x in variable_names if variable_names.count(x) > 1)
		if duplicate_variable_names:
			frappe.throw(_("Duplicate variable name: {0}").format(", ".join(duplicate_variable_names)))

	def process_resources(self):
		for resource in self.resources:
			self.validate_resources(resource)
			self.set_resource_json_fields(resource)

	def validate_resources(self, resource):
		if resource.resource_type == "API Resource" and not resource.url:
			frappe.throw(_("Please set API URL for Data Source {0}").format(resource.name))

		else:
			if resource.resource_type in ["Document", "Document List"] and not resource.document_type:
				frappe.throw(_("Please set Document Type for Data Source {0}").format(resource.name))

			if resource.resource_type == "Document List" and not resource.fields:
				frappe.throw(_("Please set fields to fetch for Data Source {0}").format(resource.name))

			if resource.resource_type == "Document":
				if resource.fetch_document_using_filters:
					if not resource.filters:
						frappe.throw(
							_("Please set filters to fetch the Data Source {0}").format(resource.name)
						)
					resource.document_name = ""
				else:
					if not resource.document_name:
						frappe.throw(
							_("Please set the document name to fetch the Data Source {0}").format(
								resource.name
							)
						)
					resource.filters = []

	def set_resource_json_fields(self, resource):
		if isinstance(resource.fields, list):
			resource.fields = frappe.as_json(resource.fields, indent=None)

		if isinstance(resource.filters, list):
			resource.filters = frappe.as_json(resource.filters, indent=None)

		if isinstance(resource.whitelisted_methods, list):
			resource.whitelisted_methods = frappe.as_json(resource.whitelisted_methods, indent=None)

	def before_export(self, doc):
		doc.name = self.get_export_docname()
		remove_null_fields(doc)

	def before_import(self):
		self.name = self.page_name

	def get_export_docname(self):
		return frappe.scrub(self.page_title)

	@frappe.whitelist()
	def publish(self, **kwargs):
		frappe.form_dict.update(kwargs)
		self.validate_conflicts_with_other_pages()
		self.published = 1
		if self.draft_blocks:
			self.blocks = self.draft_blocks
			self.draft_blocks = None
		self.save()

	def validate_conflicts_with_other_pages(self):
		other_pages = frappe.get_all(
			"Studio Page",
			filters={"studio_app": self.studio_app, "name": ["!=", self.name], "published": 1},
			or_filters=[
				["route", "=", self.route],
				["page_title", "=", self.page_title],
			],
			fields=["route", "page_title"],
		)
		if other_pages:
			frappe.throw(
				_("Page(s) with duplicate Route or Page Title already exist in this app: {0}").format(
					", ".join([f"{page.page_title} - {page.route}" for page in other_pages]),
				)
			)

	def get_folder_path(self, with_filename: bool = False) -> str:
		path = ["studio", self.studio_app, "studio_page"]
		if with_filename:
			path.append(self.get_file_name())
		return frappe.get_app_source_path(self.frappe_app, *path)

	def get_component_folder_path(self) -> str:
		path = ["studio", self.studio_app, "studio_components"]
		return frappe.get_app_source_path(self.frappe_app, *path)

	def get_file_name(self):
		return f"{self.get_export_docname()}.json"


@frappe.whitelist()
def find_page_with_route(app_name: str, page_route: str) -> str | None:
	if not page_route.startswith("/"):
		page_route = f"/{page_route}"
	try:
		return frappe.db.get_value(
			"Studio Page", dict(studio_app=app_name, route=page_route, published=1), "name", cache=True
		)
	except frappe.DoesNotExistError:
		pass


@frappe.whitelist()
def duplicate_page(page_name: str, app_name: str | None):
	if not frappe.has_permission("Studio Page", ptype="write"):
		frappe.throw("You do not have permission to duplicate a page.")

	page = frappe.get_doc("Studio Page", page_name)
	new_page = frappe.copy_doc(page)
	del new_page.page_name
	new_page.page_title = f"{new_page.page_title} Copy"
	new_page.route = None
	new_page.studio_app = app_name
	new_page.insert()

	return new_page
