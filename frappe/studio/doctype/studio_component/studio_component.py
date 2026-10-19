# Copyright (c) 2025, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists

from studio.export import (
	can_export,
	delete_file,
	parse_json,
	remove_empty_values,
	validate_standard_app_change,
	write_document_file,
)
from studio.realtime import publish_doc_change
from studio.utils import walk_blocks


class StudioComponent(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from studio.studio.doctype.studio_component_input.studio_component_input import StudioComponentInput

		block: DF.LongText | None
		component_id: DF.Data | None
		component_name: DF.Data | None
		inputs: DF.Table[StudioComponentInput]
		is_disabled: DF.Check
		is_standard: DF.Check
		studio_app: DF.Link | None
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
		# a component is standard once it is exported with its app, and stays so
		if self.studio_app and can_export(self.get_app()):
			self.is_standard = 1
		if self.is_standard and not self.studio_app:
			frappe.throw(_("A standard component must belong to a Studio App."))

	def on_update(self):
		if can_export(self):
			self.export_component()
		publish_doc_change("Studio Component", self.name)

	def on_trash(self):
		validate_standard_app_change(self)
		if can_export(self):
			delete_file(self.get_folder_path(), f"{self.name}.json")

	def export_component(self):
		frappe.create_folder(self.get_folder_path())
		write_document_file(self, folder=self.get_folder_path())

	def get_app(self):
		return frappe.get_cached_doc("Studio App", self.studio_app)

	def get_folder_path(self) -> str:
		return frappe.get_app_source_path(
			self.get_app().frappe_app, "studio", self.studio_app, "studio_components"
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
		fields=["name", "component_name", "component_id", "block", "is_disabled", "studio_app"],
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
