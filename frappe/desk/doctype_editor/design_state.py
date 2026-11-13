# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""A DocType and its layouts loaded fresh, with a Design save's edits applied in memory."""

import copy

import frappe
from frappe import _
from frappe.database.schema import SPECIAL_CHAR_PATTERN
from frappe.desk.doctype.form_layout.app_layout import read_app_layouts
from frappe.desk.doctype.form_layout.form_layout import (
	FORM_LAYOUT_TYPES,
	OMITTING_LAYOUT_TYPES,
	layout_from_fields,
	layout_type_refusal,
	parse_layout,
	parse_omitted,
	quick_entry_layout,
)
from frappe.desk.doctype_editor.errors import EditError, field_error
from frappe.desk.doctype_editor.layout_tree import LayoutTree
from frappe.model import table_fields


class EditorLayout:
	"""A site `Form Layout` row, an entry of the app file, or a layout this save adds."""

	def __init__(
		self, id: str, type: str, tabs: list, title=None, condition=None, row=None, size=None, omitted=None
	):
		self.id, self.type, self.row = id, type, row
		self.title, self.condition, self.size = title, condition, size
		self.omitted = omitted or []
		self.tree = LayoutTree(tabs, id)
		self.deleted = False

	def as_entry(self) -> dict:
		entry = {
			"title": self.title,
			"condition": self.condition,
			"layout": self.tree.tabs,
			"omitted": self.omitted,
		}
		if self.size:
			entry["size"] = self.size
		return entry


class DesignState:
	def __init__(self, doctype: str, doc=None):
		self.name = doctype
		self.doc = doc or frappe.get_doc("DocType", doctype)
		self.saved_fieldnames = {field.fieldname for field in self.doc.fields}
		self.layouts: dict[str, list[EditorLayout]] = {}
		self.touched: set[str] = set()
		self.renames: list[tuple[str, str]] = []
		self.children: dict[str, DesignState] = {}

	def add_child(self, name: str) -> "DesignState":
		"""A new child DocType, inserted before this one saves; it takes field edits only."""
		if name in self.children or frappe.db.exists("DocType", name):
			raise EditError(_("A DocType named {0} already exists.").format(name))
		doc = frappe.new_doc("DocType")
		doc.update(
			{
				"name": name,
				"module": self.doc.module,
				"custom": self.doc.custom,
				"istable": 1,
				"editable_grid": 1,
			}
		)
		self.children[name] = DesignState(name, doc)
		return self.children[name]

	@property
	def standard(self) -> bool:
		return not self.doc.custom

	def layouts_of(self, type: str) -> list[EditorLayout]:
		if self.doc.is_new():
			raise EditError(_("Save the new child table {0} before you lay it out.").format(self.name))
		if type not in self.layouts:
			if refusal := self.type_refusal(type):
				raise EditError(refusal, kind="layout", layout=type)
			self.layouts[type] = self.load_layouts(type)
		return self.layouts[type]

	def type_refusal(self, type: str) -> str | None:
		if type not in FORM_LAYOUT_TYPES:
			return _("{0} is not a layout type.").format(type)
		return layout_type_refusal(self.name, type)

	def load_layouts(self, type: str) -> list[EditorLayout]:
		if self.standard:
			app_layouts = read_app_layouts(self.name, type)
			return [
				EditorLayout(
					f"app:{index}",
					type,
					parse_layout(entry.layout),
					entry.title,
					entry.condition,
					size=entry.size,
					omitted=list(entry.omitted),
				)
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
		layout = EditorLayout(type, type, self.fallback_tabs(type))
		layouts.append(layout)
		return layout

	def add_layout(self, type: str, id: str, title=None, condition=None, start: str = "copy") -> EditorLayout:
		layouts = self.layouts_of(type)
		if not id or any(layout.id == id for layout in layouts):
			raise EditError(_("A new layout needs an id of its own."), kind="layout", layout=id)
		self.touched.add(type)
		tabs = copy.deepcopy(self.default_tabs(type)) if start == "copy" else empty_tabs()
		layout = EditorLayout(id, type, tabs, title, condition)
		layouts.append(layout)
		return layout

	def default_tabs(self, type: str) -> list:
		for layout in self.layouts_of(type):
			if not layout.deleted and not layout.condition:
				return layout.tree.tabs
		return self.fallback_tabs(type)

	def fallback_tabs(self, type: str) -> list:
		"""What the desk draws for a type with no layout of its own (`get_layouts`)."""
		if type == "Quick Entry":
			return quick_entry_layout(self.doc.fields)
		if type == "New Record":
			return copy.deepcopy(self.default_tabs("Details"))
		return layout_from_fields(self.doc.fields)

	def field(self, fieldname: str):
		for field in self.doc.fields:
			if field.fieldname == fieldname:
				return field
		if self.standard and frappe.db.exists("Custom Field", {"dt": self.name, "fieldname": fieldname}):
			raise field_error(
				_("{0} is a site custom field, so an app layout cannot place it.").format(fieldname),
				fieldname,
			)
		raise field_error(_("{0} is not a field of {1}.").format(fieldname, self.name), fieldname)

	def all_layouts(self) -> list[EditorLayout]:
		return [layout for layouts in self.layouts.values() for layout in layouts]

	def load_every_layout(self):
		if self.doc.is_new():
			return
		for type in FORM_LAYOUT_TYPES:
			if not layout_type_refusal(self.name, type):
				self.layouts_of(type)

	def touch_omitting_layouts(self):
		"""Their saved `omitted` must list a field the save adds off the layout."""
		if self.doc.is_new():
			return
		for type in OMITTING_LAYOUT_TYPES:
			if not layout_type_refusal(self.name, type) and self.layouts_of(type):
				self.touched.add(type)

	def rename_field(self, old: str, new: str):
		field = self.field(old)
		if not new:
			raise field_error(_("A field needs a fieldname."), old)
		saved = self.saved_name(old)
		if new != saved:
			self.refuse_taken_fieldname(new, old)
			self.refuse_deleted_table_rows(field, new)
		if saved:
			if self.standard:
				raise field_error(_("Renaming a saved field of a standard DocType needs a patch."), old)
			self.note_rename(saved, new)
		field.fieldname = new
		self.load_every_layout()
		for layout in self.all_layouts():
			if old in layout.tree.fieldnames() or old in layout.omitted:
				layout.tree.rename_field(old, new)
				layout.omitted = [new if each == old else each for each in layout.omitted]
				self.touched.add(layout.type)

	def refuse_taken_fieldname(self, fieldname: str, key: str | None = None):
		"""A deleted field keeps its column and data, so its name stays taken."""
		if fieldname != fieldname.lower() or SPECIAL_CHAR_PATTERN.search(fieldname):
			message = _("{0} is not a valid fieldname. Use lowercase letters, digits and underscores.")
			raise field_error(message.format(fieldname), key or fieldname)
		if any(field.fieldname == fieldname for field in self.doc.fields):
			raise field_error(
				_("{0} already has a field {1}.").format(self.name, fieldname), key or fieldname
			)
		if self.holds_deleted_data(fieldname):
			message = _("{0} still holds the data of a deleted field. Choose another fieldname.")
			raise field_error(message.format(fieldname), key or fieldname)

	def holds_deleted_data(self, fieldname: str) -> bool:
		"""A Single keeps its values in `tabSingles`; a virtual DocType has no table."""
		if self.doc.is_new() or self.doc.is_virtual:
			return False
		if self.doc.issingle:
			return bool(frappe.db.count("Singles", {"doctype": self.name, "field": fieldname}))
		return frappe.db.has_column(self.name, fieldname)

	def refuse_deleted_table_rows(self, field, fieldname: str):
		"""A deleted Table field keeps its rows, and a table of that name would show them again."""
		if field.fieldtype not in table_fields or self.doc.is_new() or not field.options:
			return
		if field.options in self.children:
			return
		if frappe.db.exists(field.options, {"parenttype": self.name, "parentfield": fieldname}):
			message = _("{0} still holds the rows of a deleted table. Choose another fieldname.")
			raise field_error(message.format(fieldname), field.fieldname)

	def saved_name(self, fieldname: str) -> str | None:
		"""The fieldname this field has in the database; None for a field added in this save."""
		for saved, renamed in self.renames:
			if renamed == fieldname:
				return saved
		return fieldname if fieldname in self.saved_fieldnames else None

	def note_rename(self, saved: str, new: str):
		"""Fold a chain of renames, so the data moves once from the saved column."""
		self.renames = [pair for pair in self.renames if pair[0] != saved]
		if new != saved:
			self.renames.append((saved, new))

	def delete_field(self, fieldname: str):
		"""Drop the field and every layout's mention of it; its column and data stay."""
		self.doc.fields.remove(self.field(fieldname))
		self.renames = [pair for pair in self.renames if pair[1] != fieldname]
		for idx, field in enumerate(self.doc.fields, start=1):
			field.idx = idx
		self.load_every_layout()
		for layout in self.all_layouts():
			if fieldname in layout.tree.fieldnames() or fieldname in layout.omitted:
				layout.tree.unplace_field(fieldname)
				layout.omitted = [each for each in layout.omitted if each != fieldname]
				self.touched.add(layout.type)


def empty_tabs() -> list:
	return [
		{
			"name": "first_tab",
			"sections": [{"name": "section_1", "columns": [{"name": "column_1", "fields": []}]}],
		}
	]
