# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""Each edit act in Customize mode: the Design acts, written to the site tier (#45865)."""

import copy

import frappe
from frappe import _
from frappe.database.schema import SPECIAL_CHAR_PATTERN
from frappe.desk.doctype_editor.customize_state import ANCHORED_TYPES, CustomizeState
from frappe.desk.doctype_editor.design_edits import DesignEdits, refuse_property
from frappe.desk.doctype_editor.errors import EditError, field_error
from frappe.desk.doctype_editor.layout_tree import LayoutTree


class CustomizeEdits(DesignEdits):
	state: CustomizeState

	def apply(self, edit: dict):
		act = edit.get("act") if isinstance(edit, dict) else None
		if (act or "").startswith("settings."):
			raise EditError(_("{0} is not in Customize mode yet.").format(act))
		super().apply(edit)

	def canvas(self, edit: dict, method: str, keys: tuple):
		if method == "place_field" and self.place_without_fork(edit, keys):
			return
		super().canvas(edit, method, keys)
		ref = edit.get("layout") or {}
		fieldname = edit.get("fieldname")
		if method == "place_field" and ref.get("type") in ANCHORED_TYPES:
			if self.state.is_site_custom(self.state.field(fieldname)):
				self.state.anchor(fieldname, self.state.layout(ref).tree.tabs)

	def place_without_fork(self, edit: dict, keys: tuple) -> bool:
		"""A custom field takes an anchor; a standard one on a break-drawn Details reorders the fields."""
		ref = edit.get("layout") or {}
		type = ref.get("type")
		if type not in ANCHORED_TYPES or self.state.forked(type):
			return False
		default = self.state.default_layout(type)
		if ref.get("id") and (not default or ref["id"] != default.id):
			return False
		field = self.state.field(edit.get("fieldname"))
		if self.state.is_site_custom(field):
			tree = self.placed(copy.deepcopy(self.state.default_tabs(type)), edit, keys)
			self.state.anchor(field.fieldname, tree.tabs)
			return True
		if type == "Details" and not default:
			self.state.order_fields(self.placed(self.state.fallback_tabs(type), edit, keys).tabs)
			return True
		return False

	def placed(self, tabs: list, edit: dict, keys: tuple) -> LayoutTree:
		tree = LayoutTree(tabs, edit["layout"]["type"])
		tree.place_field(**{key: edit.get(key) for key in keys if key in edit})
		return tree

	def fields_add_field(self, edit: dict):
		fieldname = edit.get("fieldname") or SPECIAL_CHAR_PATTERN.sub("", frappe.scrub(edit.get("label") or ""))
		if not fieldname.startswith("custom_"):
			fieldname = f"custom_{fieldname}"
		super().fields_add_field({**edit, "fieldname": fieldname})
		self.state.field(fieldname).is_custom_field = 1
		if not edit.get("layout") and self.state.layouts_of("Details"):
			self.state.anchors[fieldname] = None

	def fields_reset_field_property(self, edit: dict):
		"""Back to the app's value, so Customize Form deletes that one Property Setter."""
		fieldname, property = edit.get("fieldname"), edit.get("property")
		field = self.state.field(fieldname)
		refuse_property(fieldname, property)
		if self.state.is_site_custom(field):
			raise field_error(_("Only a standard field's property can be reset."), fieldname, property)
		if not field.meta.has_field(property):
			self.state.property_deletes.append((fieldname, property))
			return
		filters = {"parent": self.state.name, "fieldname": fieldname}
		field.set(property, frappe.db.get_value("DocField", filters, property))

	def layouts_reset_to_app(self, edit: dict):
		self.state.reset_to_app(edit.get("type"))
