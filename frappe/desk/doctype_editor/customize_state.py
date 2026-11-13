# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""A standard DocType as Customize Form loads it, with a Customize save's edits applied in memory."""

import copy

import frappe
from frappe import _
from frappe.desk.doctype.form_layout.form_layout import (
	OMITTING_LAYOUT_TYPES,
	layout_from_fields,
	layout_type_refusal,
	quick_entry_layout,
)
from frappe.desk.doctype_editor.design_state import DesignState, EditorLayout
from frappe.desk.doctype_editor.errors import EditError, field_error

# A custom field on these renders at its anchor (`insert_after`) until the site forks the layout.
ANCHORED_TYPES = ("Details", "New Record")


class CustomizeState(DesignState):
	"""`doc` is the Customize Form; a type with no site row shows its app or fallback layout until touched."""

	def __init__(self, doctype: str):
		form = frappe.get_doc("Customize Form")
		form.doc_type = doctype
		form.fetch_to_customize()
		super().__init__(doctype, form)
		self.anchors: dict[str, str | None] = {}
		self.reset_rows: list[str] = []
		self.property_deletes: list[tuple[str, str]] = []

	@property
	def standard(self) -> bool:
		return False

	def child_defaults(self) -> dict:
		return {"module": frappe.get_meta(self.name).module, "custom": 1}

	def load_layouts(self, type: str) -> list[EditorLayout]:
		return self.site_layouts(type) or self.app_file_layouts(type)

	def forked(self, type: str) -> bool:
		return any(layout.row for layout in self.layouts_of(type))

	def layout(self, ref: dict) -> EditorLayout:
		id = (ref or {}).get("id")
		if id and frappe.db.exists("Form Layout", {"name": id, "app": ("is", "set")}):
			raise EditError(
				_("An app made this layout, so Customize cannot change it."), kind="layout", layout=id
			)
		return super().layout(ref)

	def default_layout(self, type: str) -> EditorLayout | None:
		return next((each for each in self.layouts_of(type) if not each.deleted and not each.condition), None)

	def fallback_tabs(self, type: str) -> list:
		"""A fork leaves out the site's custom fields: they keep rendering at their anchors (#45865 r9)."""
		if type == "New Record":
			return copy.deepcopy(self.default_tabs("Details"))
		fields = [field for field in self.doc.fields if not self.is_site_custom(field)]
		return quick_entry_layout(fields) if type == "Quick Entry" else layout_from_fields(fields)

	def touch_omitting_layouts(self):
		"""Only a site row lists what it omits; an app or fallback layout stays unforked."""
		for type in OMITTING_LAYOUT_TYPES:
			if not layout_type_refusal(self.name, type) and self.forked(type):
				self.touched.add(type)

	def reset_to_app(self, type: str):
		self.reset_rows += [layout.row for layout in self.layouts_of(type) if layout.row]
		self.layouts[type] = self.app_file_layouts(type)
		self.touched.discard(type)

	def is_site_custom(self, field) -> bool:
		if field.fieldname not in self.saved_fieldnames:
			return True
		return bool(field.get("is_custom_field") and not field.get("is_system_generated"))

	def anchor(self, fieldname: str, tabs: list):
		"""The field drawn before it in its column, or the column's name when it is first (#45865 r1, r7)."""
		for tab in tabs:
			for section in tab["sections"]:
				for column in section["columns"]:
					if fieldname in column["fields"]:
						index = column["fields"].index(fieldname)
						self.set_anchor(fieldname, column["fields"][index - 1] if index else column["name"])
						return

	def set_anchor(self, fieldname: str, anchor: str | None):
		"""Customize Form resets `insert_after` to the row before, so the row moves after a field anchor."""
		self.anchors[fieldname] = anchor
		fields = self.doc.fields
		after = next((field for field in fields if field.fieldname == anchor), None)
		if after:
			field = self.field(fieldname)
			fields.remove(field)
			fields.insert(fields.index(after) + 1, field)
			self.reindex()

	def order_fields(self, tabs: list):
		"""Make the form's rows follow a fallback tree; a field the tree leaves out stays after its neighbour."""
		by_name = {field.fieldname: field for field in self.doc.fields}
		names = [
			name
			for tab in tabs
			for section in tab["sections"]
			for name in (tab["name"], section["name"], *column_names(section))
		]
		ordered = [by_name.pop(name) for name in names if name in by_name]
		previous = None
		for field in self.doc.fields:
			if field not in ordered:
				ordered.insert(ordered.index(previous) + 1 if previous else 0, field)
			previous = field
		self.doc.fields = ordered
		self.reindex()

	def reindex(self):
		for idx, field in enumerate(self.doc.fields, start=1):
			field.idx = idx

	def rename_field(self, old: str, new: str):
		self.refuse_standard(old, _("Only a custom field this site added can be renamed."))
		super().rename_field(old, new)

	def delete_field(self, fieldname: str):
		self.refuse_standard(fieldname, _("{0} is a standard field. Hide it instead.").format(fieldname))
		super().delete_field(fieldname)

	def refuse_standard(self, fieldname: str, message: str):
		if not self.is_site_custom(self.field(fieldname)):
			raise field_error(message, fieldname)

	def holds_deleted_data(self, fieldname: str) -> bool:
		return not frappe.get_meta(self.name).is_virtual and frappe.db.has_column(self.name, fieldname)


def column_names(section: dict) -> list[str]:
	return [name for column in section["columns"] for name in (column["name"], *column["fields"])]
