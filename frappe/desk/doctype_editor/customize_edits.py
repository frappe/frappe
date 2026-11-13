# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""Each edit act in Customize mode: the Design acts, written to the site tier."""

import copy

import frappe
from frappe import _
from frappe.database.schema import SPECIAL_CHAR_PATTERN
from frappe.desk.doctype_editor.customize_state import ANCHORED_TYPES, CustomizeState
from frappe.desk.doctype_editor.design_edits import DesignEdits, refuse_property
from frappe.desk.doctype_editor.errors import field_error
from frappe.desk.doctype_editor.layout_tree import LayoutTree
from frappe.desk.doctype_editor.mode import permissions_refusal
from frappe.desk.doctype_editor.settings_edits import AUTOINCREMENT, CUSTOMIZE_PROPERTIES, setting_error

PERMISSION_ACTS = (
	"settings.add_permission",
	"settings.remove_permission",
	"settings.set_permission",
	"settings.reset_permissions",
)


class CustomizeEdits(DesignEdits):
	state: CustomizeState

	properties = CUSTOMIZE_PROPERTIES

	def apply(self, edit: dict):
		if isinstance(edit, dict) and edit.get("act") in PERMISSION_ACTS and (refusal := permissions_refusal()):
			raise setting_error(refusal, "permissions")
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
		drawn = self.state.drawn_tabs(type)
		tree = self.placed(copy.deepcopy(drawn), edit, keys)
		if self.state.is_site_custom(field):
			self.state.anchor(field.fieldname, tree.tabs)
			return True
		if type == "Details" and not default:
			self.state.order_fields(tree.tabs)
			self.state.follow_drawn_order(drawn, tree.tabs)
			return True
		return False

	def placed(self, tabs: list, edit: dict, keys: tuple) -> LayoutTree:
		tree = LayoutTree(tabs, edit["layout"]["type"])
		tree.place_field(**{key: edit.get(key) for key in keys if key in edit})
		return tree

	def fields_add_field(self, edit: dict):
		fieldname = edit.get("fieldname") or SPECIAL_CHAR_PATTERN.sub(
			"", frappe.scrub(edit.get("label") or "")
		)
		if not fieldname.startswith("custom_"):
			fieldname = f"custom_{fieldname}"
		super().fields_add_field({**edit, "fieldname": fieldname})
		self.state.field(fieldname).is_custom_field = 1
		if not edit.get("layout") and self.state.layouts_of("Details"):
			self.state.anchors[fieldname] = None

	def fields_set_field_property(self, edit: dict):
		super().fields_set_field_property(edit)
		# A queued reset deletes its setter after the save, so a later edit must cancel it.
		key = (edit.get("fieldname"), edit.get("property"))
		if key in self.state.property_deletes:
			self.state.property_deletes.remove(key)

	def fields_reset_field_property(self, edit: dict):
		"""Back to the app's value, so Customize Form deletes that one Property Setter; an app's setter stays."""
		fieldname, property = edit.get("fieldname"), edit.get("property")
		field = self.state.field(fieldname)
		refuse_property(fieldname, property)
		if self.state.is_site_custom(field):
			raise field_error(_("Only a standard field's property can be reset."), fieldname, property)
		if self.is_app_setter(fieldname, property):
			if field.meta.has_field(property):
				field.set(property, frappe.get_meta(self.state.name).get_field(fieldname).get(property))
			return
		if not field.meta.has_field(property) or field.is_custom_field:
			# An app's Custom Field keeps its value on its own row; the setter is what overrides it.
			if field.meta.has_field(property):
				filters = {"dt": self.state.name, "fieldname": fieldname}
				field.set(property, frappe.db.get_value("Custom Field", filters, property))
			self.state.property_deletes.append((fieldname, property))
			return
		filters = {"parent": self.state.name, "fieldname": fieldname}
		field.set(property, frappe.db.get_value("DocField", filters, property))

	def layouts_reset_to_app(self, edit: dict):
		self.state.reset_to_app(edit.get("type"))

	def settings_reset_doctype_property(self, edit: dict):
		"""Back to the app's value, so Customize Form deletes the site's Property Setter; an app's setter stays."""
		property = edit.get("property")
		self.refuse_property(property)
		if self.is_app_setter(None, property):
			value = frappe.get_meta(self.state.name).get(property)
		else:
			value = frappe.db.get_value("DocType", self.state.name, property)
		self.state.doc.set(property, value)

	def settings_reset_permissions(self, edit: dict):
		self.state.permissions = None
		self.state.reset_permissions = True

	def refuse_autoincrement(self, value: str):
		if AUTOINCREMENT in (value, self.saved_autoname()) and value != self.saved_autoname():
			raise setting_error(_("Customize cannot switch to or from Number in order."), "autoname")

	def saved_autoname(self) -> str | None:
		return frappe.get_meta(self.state.name).autoname

	def series_field(self):
		if field := self.state.doc.get("fields", {"fieldname": "naming_series"}):
			return field[0]
		raise setting_error(_("{0} has no naming_series field.").format(self.state.name), "naming_series")

	def permission_rows(self) -> list:
		"""The first edit copies the rows the site uses now: its own, else the app's."""
		if self.state.permissions is None:
			self.state.permissions = [
				frappe.new_doc("Custom DocPerm").update(row) for row in self.state.starting_permissions()
			]
		return self.state.permissions

	def append_permission(self, values: dict):
		self.permission_rows().append(frappe.new_doc("Custom DocPerm").update(values))

	def drop_permission(self, row):
		"""With no rows of its own the site would fall back to the app's: removing the last is a reset."""
		rows = self.permission_rows()
		if len(rows) == 1:
			raise setting_error(_("Keep at least one permission rule."), "permissions")
		rows.remove(row)

	def is_app_setter(self, fieldname: str | None, property: str) -> bool:
		"""`fieldname` None names a setter of the DocType's own property."""
		filters = {"doc_type": self.state.name, "property": property}
		filters |= {"field_name": fieldname} if fieldname else {"doctype_or_field": "DocType"}
		return bool(frappe.db.get_value("Property Setter", filters, "is_system_generated"))
