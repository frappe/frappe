# Copyright (c) 2025, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import os

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists
from frappe.studio.export import delete_file, parse_json, remove_empty_values, validate_standard_app_change
from frappe.studio.realtime import publish_doc_change
from frappe.studio.sync_json import get_studio_folders
from frappe.studio.utils import validate_file_name, walk_blocks


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
		publish_doc_change("Studio Component", self.name)

	def on_trash(self):
		validate_standard_app_change(self)
		if frappe.conf.developer_mode:
			self.delete_files()

	def delete_files(self):
		"""Every standard page using a component exports it, so its file can be in several apps"""
		for folder in get_studio_folders():
			for app_folder in os.listdir(folder):
				delete_file(folder, app_folder, "studio_components", f"{frappe.scrub(self.name)}.json")


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
		fields=["name", "component_name", "component_id", "block", "is_disabled"],
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
