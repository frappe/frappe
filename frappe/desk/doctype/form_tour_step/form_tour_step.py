# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

# import frappe
from frappe.model.document import Document


class FormTourStep(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		child_doctype: DF.Data | None
		description: DF.HTMLEditor
		element_selector: DF.Data | None
		fieldname: DF.Literal[None]
		fieldtype: DF.Data | None
		has_next_condition: DF.Check
		hide_buttons: DF.Check
		is_table_field: DF.Check
		label: DF.Data | None
		modal_trigger: DF.Check
		next_form_tour: DF.Link | None
		next_on_click: DF.Check
		next_step_condition: DF.Code | None
		offset_x: DF.Int
		offset_y: DF.Int
		ondemand_description: DF.HTMLEditor | None
		parent: DF.Data
		parent_element_selector: DF.Data | None
		parent_fieldname: DF.Literal[None]
		parentfield: DF.Data
		parenttype: DF.Data
		popover_element: DF.Check
		position: DF.Literal[
			"Left",
			"Left Center",
			"Left Bottom",
			"Top",
			"Top Center",
			"Top Right",
			"Right",
			"Right Center",
			"Right Bottom",
			"Bottom",
			"Bottom Center",
			"Bottom Right",
			"Mid Center",
		]
		title: DF.Data
		ui_tour: DF.Check
	# end: auto-generated types

	pass
