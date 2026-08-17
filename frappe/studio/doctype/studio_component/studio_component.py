# Copyright (c) 2025, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import os

import frappe
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists

from studio.export import delete_file, parse_json
from studio.realtime import publish_doc_change


class StudioComponent(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		from studio.studio.doctype.studio_component_input.studio_component_input import StudioComponentInput

		block: DF.JSON | None
		component_id: DF.Data | None
		component_name: DF.Data | None
		inputs: DF.Table[StudioComponentInput]
		is_disabled: DF.Check
	# end: auto-generated types

	def before_insert(self):
		if not self.component_id:
			self.component_id = append_number_if_name_exists(
				"Studio Component", frappe.scrub(self.component_name)
			)

	def before_export(self, doc):
		doc.block = parse_json(doc.block)

	def on_update(self):
		publish_doc_change("Studio Component", self.name)

	@frappe.whitelist()
	def delete_component(self, studio_app: str | None = None):
		self.delete()
		if not studio_app:
			return

		app = frappe.db.get_value("Studio App", studio_app, ["frappe_app", "is_standard"], as_dict=True)
		if app.is_standard:
			app_path = frappe.get_app_source_path(app.frappe_app, "studio", studio_app, "studio_components")
			component_path = os.path.join(app_path, f"{self.component_id}.json")
			print("Deleting component file at:", component_path)
			delete_file(component_path)


COMPONENT_INPUT_FIELDS = ("input_name", "type", "description", "options", "required", "default")


@frappe.whitelist(methods=["GET"])
def get_component(component_name: str) -> dict:
	"""Serve a component definition to the app renderer without a DocType permission
	check — like page definitions (see get_page), a component is markup with no draft
	state; the data it renders stays permission-checked by the endpoints serving it."""
	component = frappe.get_cached_doc("Studio Component", component_name)
	return {
		"name": component.name,
		"component_name": component.component_name,
		"component_id": component.component_id,
		"block": component.block,
		"is_disabled": component.is_disabled,
		"inputs": [
			{"name": row.name, **{field: row.get(field) for field in COMPONENT_INPUT_FIELDS}}
			for row in component.inputs
		],
	}
