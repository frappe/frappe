# Copyright (c) 2024, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt
import os

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists

from studio.export import (
	can_export,
	delete_folder,
	parse_json,
	remove_null_fields,
	write_code_file,
	write_document_file,
)
from studio.utils import camel_case_to_kebab_case


class StudioPage(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from studio.studio.doctype.studio_page_resource.studio_page_resource import StudioPageResource
		from studio.studio.doctype.studio_page_variable.studio_page_variable import StudioPageVariable

		blocks: DF.LongText | None
		draft_blocks: DF.LongText | None
		frappe_app: DF.Literal[None]
		is_standard: DF.Check
		page_name: DF.Data | None
		page_title: DF.Data | None
		published: DF.Check
		resources: DF.Table[StudioPageResource]
		route: DF.Data | None
		script: DF.Code | None
		studio_app: DF.Link | None
		variables: DF.Table[StudioPageVariable]
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
			# each page lives in its own folder: studio/<app>/studio_page/<scrubbed_title>/
			frappe.create_folder(self.get_folder_path())
			# script lives in the companion .ts (code mode), so keep it out of the JSON
			write_document_file(self, folder=self.get_folder_path(), exclude_fields=["script"])
			self.relocate_on_retitle()
			self.export_components()

	def export_script_to_file(self):
		"""Move the page script into its companion <page>.ts and clear the DB `script` field. Called on enabling exports"""
		if not self.script:
			return
		folder = self.get_folder_path()
		frappe.create_folder(folder)
		stem = self.get_export_docname()
		if not os.path.exists(os.path.join(folder, f"{stem}.ts")):
			write_code_file(self, folder, code_field="script", extension="ts", filename=stem)
		self.db_set("script", None, update_modified=False)

	def restore_script_from_file(self):
		"""Load the exported <page>.ts back into the `script` field, so the code survives in DB-only
		mode (called before the export folder is deleted on un-export)."""
		ts_path = os.path.join(self.get_folder_path(), f"{self.get_export_docname()}.ts")
		if os.path.exists(ts_path):
			self.db_set("script", frappe.read_file(ts_path), update_modified=False)

	def relocate_on_retitle(self):
		"""The page folder and its files are named after the page title, so a retitle relocates them.
		The JSON is regenerated under the new name; carry the companion <page>.ts over too, then
		remove the old folder."""
		if not self.has_value_changed("page_title"):
			return
		doc_before_save = self.get_doc_before_save()
		if not doc_before_save:
			return

		old_stem = frappe.scrub(doc_before_save.page_title)
		old_folder = frappe.get_app_source_path(
			self.frappe_app, "studio", self.studio_app, "studio_page", old_stem
		)
		old_page_script = os.path.join(old_folder, f"{old_stem}.ts")
		if os.path.exists(old_page_script):
			os.rename(
				old_page_script, os.path.join(self.get_folder_path(), f"{self.get_export_docname()}.ts")
			)
		delete_folder(old_folder)

	def export_components(self):
		if components := self.get_studio_components():
			folder = self.get_component_folder_path()
			frappe.create_folder(folder)
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

		if self.has_blocks():
			root_block = get_root_block(self.blocks)
			add_component(root_block)
		if self.has_blocks(check_draft=True):
			root_block = get_root_block(self.draft_blocks)
			add_component(root_block)

		return components

	def has_blocks(self, check_draft: bool = False):
		if check_draft:
			if self.draft_blocks and self.draft_blocks != "[]":
				return True
		elif self.blocks and self.blocks != "[]":
			return True
		return False

	def on_trash(self):
		self.delete_ai_sessions()
		if can_export(self):
			delete_folder(self.get_folder_path())

	def delete_ai_sessions(self):
		for session in frappe.get_all("Studio AI Session", filters={"page": self.name}, pluck="name"):
			frappe.delete_doc("Studio AI Session", session, ignore_missing=True)

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

		if isinstance(resource.params, list):
			resource.params = frappe.as_json(resource.params, indent=None)

	def before_export(self, doc):
		doc.name = self.get_export_docname()
		doc.blocks = parse_json(doc.blocks)
		doc.draft_blocks = parse_json(doc.draft_blocks)

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

	@frappe.whitelist()
	def unpublish(self):
		self.published = 0
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
		# each page exports to its own folder: studio/<app>/studio_page/<scrubbed_title>/
		path = ["studio", self.studio_app, "studio_page", self.get_export_docname()]
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
			"Studio Page", dict(studio_app=app_name, route=page_route), "name", cache=True
		)
	except frappe.DoesNotExistError:
		pass


@frappe.whitelist()
def duplicate_page(page_name: str, app_name: str | None):
	if not frappe.has_permission("Studio Page", ptype="write"):
		frappe.throw(_("You do not have permission to duplicate a page."))

	page = frappe.get_doc("Studio Page", page_name)
	new_page = frappe.copy_doc(page)
	del new_page.page_name
	new_page.page_title = f"{new_page.page_title} Copy"
	new_page.route = None
	new_page.studio_app = app_name
	new_page.insert()

	return new_page
