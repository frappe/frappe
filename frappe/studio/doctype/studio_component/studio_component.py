# Copyright (c) 2025, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import os

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists
from frappe.studio.export import (
	can_export,
	delete_file,
	parse_json,
	remove_empty_values,
	validate_standard_app_change,
	write_code_file,
	write_document_file,
)
from frappe.studio.realtime import publish_doc_change
from frappe.studio.sync_json import COMPONENT_FOLDER, get_studio_folders
from frappe.studio.utils import find_script_file, script_extension, validate_file_name, walk_blocks


class StudioComponent(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.studio.doctype.studio_component_input.studio_component_input import StudioComponentInput
		from frappe.types import DF

		block: DF.LongText | None
		component_id: DF.Data | None
		component_name: DF.Data | None
		inputs: DF.Table[StudioComponentInput]
		is_disabled: DF.Check
		is_standard: DF.Check
		script: DF.Code | None
	# end: auto-generated types

	def before_insert(self):
		if not self.component_id:
			self.component_id = append_number_if_name_exists(
				"Studio Component", frappe.scrub(self.component_name)
			)

	def before_export(self, doc):
		doc.block = parse_json(doc.block)
		if doc.block:
			remove_empty_values(doc.block)

	def before_validate(self):
		if isinstance(self.block, dict):
			self.block = frappe.as_json(self.block, indent=None)

	def validate(self):
		validate_standard_app_change(self)
		self.validate_component_id()

	def validate_component_id(self):
		# the scrubbed id names the component's exported file, so it must stay a single path segment
		validate_file_name(
			self.name,
			_("Component ID cannot be empty or contain slashes."),
			title=_("Invalid Component ID"),
		)

	def on_update(self):
		if can_export(self) and self.has_value_changed("script"):
			for folder in self.get_export_folders():
				self.write_script_file(folder)
		publish_doc_change("Studio Component", self.name)

	def on_trash(self):
		validate_standard_app_change(self)
		if frappe.conf.developer_mode:
			self.delete_files()

	def export_to_folder(self, folder: str):
		"""Write the component's JSON, and its script when the folder has none.

		The script file is the copy a developer edits, so only a changed `script` field replaces it."""
		write_document_file(self, folder=folder, exclude_fields=["script"])
		if self.script and not os.path.exists(self.get_script_file_path(folder)):
			self.write_script_file(folder)

	def write_script_file(self, folder: str):
		"""An existing file keeps its language. A new one is JavaScript, the language of the `script` field."""
		stem = frappe.scrub(self.name)
		if self.script:
			extension = script_extension(folder, stem, default="js")
			write_code_file(self, folder, code_field="script", extension=extension, filename=stem)
		else:
			delete_file(self.get_script_file_path(folder))

	def get_script_file_path(self, folder: str) -> str:
		return find_script_file(folder, frappe.scrub(self.name))

	def get_export_folders(self) -> list[str]:
		"""Every standard page using a component exports it, so its files can be in several apps"""
		folders = []
		for studio_folder in get_studio_folders():
			for app_folder in os.listdir(studio_folder):
				folder = os.path.join(studio_folder, app_folder, COMPONENT_FOLDER)
				if os.path.exists(os.path.join(folder, f"{frappe.scrub(self.name)}.json")):
					folders.append(folder)
		return folders

	def delete_files(self):
		for folder in self.get_export_folders():
			delete_component_files(folder, frappe.scrub(self.name))


def delete_component_files(folder: str, stem: str):
	delete_file(find_script_file(folder, stem))
	delete_file(folder, f"{stem}.json")


def mark_components_standard(names: list[str]):
	"""A component with a file in an app is standard, whether or not the file says so"""
	frappe.db.set_value(
		"Studio Component", {"name": ["in", names], "is_standard": 0}, "is_standard", 1, update_modified=False
	)


def get_components_for_blocks(blocks) -> list[dict]:
	"""Fetch component definitions referenced by a block tree, one depth at a time."""
	components = []
	requested_components = set()
	to_fetch = extract_component_names(blocks)
	while to_fetch:
		requested_components.update(to_fetch)
		batch = fetch_component_batch(to_fetch)
		components.extend(batch)
		to_fetch = get_nested_component_names(batch) - requested_components
	return components


def extract_component_names(blocks) -> set[str]:
	return {
		block["componentName"]
		for block in walk_blocks(blocks)
		if block.get("isStudioComponent") and block.get("componentName")
	}


def get_nested_component_names(components) -> set[str]:
	names = set()
	for component in components:
		names.update(extract_component_names(component["block"]))
	return names


def fetch_component_batch(names: set[str]) -> list[dict]:
	components = frappe.get_all(
		"Studio Component",
		filters={"name": ["in", names]},
		fields=["name", "component_name", "component_id", "block", "script", "is_disabled"],
	)
	if not components:
		return []

	inputs_by_component = {}
	input_rows = frappe.get_all(
		"Studio Component Input",
		filters={"parenttype": "Studio Component", "parent": ["in", [c.name for c in components]]},
		fields=["name", "parent", "input_name", "type", "description", "options", "required", "default"],
		order_by="idx asc",
	)
	for row in input_rows:
		inputs_by_component.setdefault(row.pop("parent"), []).append(row)

	for component in components:
		component["inputs"] = inputs_by_component.get(component.name, [])
	return components
