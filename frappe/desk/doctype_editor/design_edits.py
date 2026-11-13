# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""Each Design edit act applied to a `DesignState` in memory (inventory section A)."""

import frappe
from frappe import _
from frappe.desk.doctype_editor.design_state import DesignState
from frappe.desk.doctype_editor.errors import EditError, field_error

PLACE_KEYS = ("fieldname", "section", "column", "index", "tab")
# A column is named with its section: column names repeat across sections.
CANVAS_ACTS = {
	"canvas.add_tab": ("add_tab", ("name", "label", "index")),
	"canvas.remove_tab": ("remove_tab", ("tab",)),
	"canvas.move_tab": ("move_tab", ("tab", "index")),
	"canvas.add_section": ("add_section", ("tab", "name", "label", "index")),
	"canvas.remove_section": ("remove_section", ("section",)),
	"canvas.move_section": ("move_section", ("section", "tab", "index")),
	"canvas.add_column": ("add_column", ("section", "name", "index")),
	"canvas.remove_column": ("remove_column", ("column", "section")),
	"canvas.move_column": ("move_column", ("column", "section", "to_section", "index")),
	"canvas.set_container_property": ("set_container_property", ("container", "section", "property", "value")),
	"canvas.place_field": ("place_field", PLACE_KEYS),
	"canvas.move_field": ("place_field", PLACE_KEYS),
	"canvas.unplace_field": ("unplace_field", ("fieldname",)),
}


class DesignEdits:
	def __init__(self, state: DesignState):
		self.state = state

	def apply(self, edit: dict):
		act = edit.get("act") if isinstance(edit, dict) else None
		if act in CANVAS_ACTS:
			return self.canvas(edit, *CANVAS_ACTS[act])
		method = getattr(self, (act or "").replace(".", "_"), None)
		if not method or not act.startswith(("fields.", "layouts.")):
			raise EditError(_("{0} is not a Design edit.").format(act))
		method(edit)

	def canvas(self, edit: dict, method: str, keys: tuple):
		layout = self.state.layout(edit.get("layout"))
		if "fieldname" in keys:
			self.state.field(edit.get("fieldname"))
		getattr(layout.tree, method)(**{key: edit.get(key) for key in keys if key in edit})

	def fields_add_field(self, edit: dict):
		label, fieldtype = edit.get("label"), edit.get("fieldtype")
		if not label or not fieldtype:
			raise EditError(_("A new field needs a label and a type."))
		fieldname = edit.get("fieldname") or frappe.scrub(label)
		if any(field.fieldname == fieldname for field in self.state.doc.fields):
			raise field_error(_("{0} already has a field {1}.").format(self.state.name, fieldname), fieldname)
		properties = edit.get("properties") or {}
		self.state.doc.append(
			"fields", {**properties, "fieldname": fieldname, "label": label, "fieldtype": fieldtype, "options": edit.get("options")}
		)
		if edit.get("layout"):
			self.canvas({**edit, "fieldname": fieldname}, "place_field", PLACE_KEYS)
