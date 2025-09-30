# Copyright (c) 2025, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import os

import frappe
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists

from studio.export import delete_file


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
