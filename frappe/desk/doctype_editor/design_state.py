# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""A DocType and its layouts loaded fresh, with a Design save's edits applied in memory."""

import frappe
from frappe import _
from frappe.desk.doctype.form_layout.app_layout import read_app_layouts
from frappe.desk.doctype.form_layout.form_layout import (
	layout_from_fields,
	layout_type_refusal,
	parse_layout,
	parse_omitted,
	validate_target,
)
from frappe.desk.doctype_editor.errors import EditError, field_error
from frappe.desk.doctype_editor.layout_tree import LayoutTree


class EditorLayout:
	"""A site `Form Layout` row, an entry of the app file, or a layout this save adds."""

	def __init__(self, id: str, type: str, tabs: list, title=None, condition=None, row=None, size=None, omitted=None):
		self.id, self.type, self.row = id, type, row
		self.title, self.condition, self.size = title, condition, size
		self.omitted = omitted or []
		self.tree = LayoutTree(tabs, id)
		self.deleted = False

	def as_entry(self) -> dict:
		entry = {"title": self.title, "condition": self.condition, "layout": self.tree.tabs}
		if self.size:
			entry["size"] = self.size
		return entry


class DesignState:
	def __init__(self, doctype: str, pending: "DesignState | None" = None):
		self.name = doctype
		self.doc = frappe.get_doc("DocType", doctype)
		self.saved_fieldnames = {field.fieldname for field in self.doc.fields}
		self.layouts: dict[str, list[EditorLayout]] = {}
		self.touched: set[str] = set()
		self.renames: list[tuple[str, str]] = []

	@property
	def standard(self) -> bool:
		return not self.doc.custom

	def layouts_of(self, type: str) -> list[EditorLayout]:
		if type not in self.layouts:
			validate_target(self.name, type)
			self.layouts[type] = self.load_layouts(type)
		return self.layouts[type]

	def load_layouts(self, type: str) -> list[EditorLayout]:
		if self.standard:
			app_layouts = read_app_layouts(self.name, type)
			return [
				EditorLayout(f"app:{index}", type, parse_layout(entry.layout), entry.title, entry.condition, size=entry.size)
				for index, entry in enumerate(app_layouts.entries if app_layouts else ())
			]
		rows = frappe.get_all(
			"Form Layout",
			filters={"dt": self.name, "type": type, "app": ("is", "not set")},
			fields=["name", "title", "condition", "layout", "dialog_size", "omitted"],
			order_by="creation asc",
		)
		return [
			EditorLayout(
				row.name,
				type,
				parse_layout(row.layout),
				row.title,
				row.condition,
				row.name,
				row.dialog_size,
				parse_omitted(row.omitted),
			)
			for row in rows
		]

	def layout(self, ref: dict) -> EditorLayout:
		"""The layout an edit names; no `id` is the type's default, made from the fallback when missing."""
		type = (ref or {}).get("type")
		layouts = self.layouts_of(type)
		self.touched.add(type)
		id = ref.get("id")
		for layout in layouts:
			if not layout.deleted and (layout.id == id if id else not layout.condition):
				return layout
		if id:
			raise EditError(_("This {0} layout no longer exists.").format(_(type)), kind="layout", layout=id)
		layout = EditorLayout(type, type, layout_from_fields(self.doc.fields))
		layouts.append(layout)
		return layout

	def field(self, fieldname: str):
		for field in self.doc.fields:
			if field.fieldname == fieldname:
				return field
		raise field_error(_("{0} is not a field of {1}.").format(fieldname, self.name), fieldname)

	def all_layouts(self) -> list[EditorLayout]:
		return [layout for layouts in self.layouts.values() for layout in layouts]

	def load_every_layout(self):
		from frappe.desk.doctype.form_layout.form_layout import FORM_LAYOUT_TYPES

		for type in FORM_LAYOUT_TYPES:
			if not layout_type_refusal(self.name, type):
				self.layouts_of(type)

	def delete_field(self, fieldname: str):
		"""Drop the field and every layout's mention of it; its column and data stay."""
		self.doc.fields.remove(self.field(fieldname))
		for idx, field in enumerate(self.doc.fields, start=1):
			field.idx = idx
		self.load_every_layout()
		for layout in self.all_layouts():
			if fieldname in layout.tree.fieldnames() or fieldname in layout.omitted:
				layout.tree.unplace_field(fieldname)
				layout.omitted = [each for each in layout.omitted if each != fieldname]
				self.touched.add(layout.type)
