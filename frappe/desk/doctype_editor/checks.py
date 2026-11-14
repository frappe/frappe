# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""What a Design save checks before its first write: a DocType's DDL commits, so a later refusal cannot undo it."""

from functools import cached_property

import frappe
from frappe import _
from frappe.desk.doctype.form_layout.form_layout import (
	LAYOUT_BREAKS,
	inline_fields,
	refuse_field_name,
	validate_inline_field,
)
from frappe.desk.doctype_editor.design_state import DesignState, EditorLayout
from frappe.desk.doctype_editor.errors import EditError
from frappe.model.meta import Meta, clear_meta_cache

CHECK_SAVEPOINT = "doctype_editor_check"


class DesignChecks:
	def __init__(self, state: DesignState):
		self.state = state

	def errors(self) -> list[dict]:
		messages = len(frappe.local.message_log)
		try:
			return [*self.doctype_errors(), *self.layout_errors()]
		finally:
			del frappe.local.message_log[messages:]

	def doctype_errors(self) -> list[dict]:
		"""Each DocType's validation; the new child tables' rows let the parent's Table fields name them."""
		frappe.db.savepoint(CHECK_SAVEPOINT)
		try:
			return self.child_errors() or self.parent_errors()
		except frappe.ValidationError as e:
			return [EditError(str(e)).as_dict()]
		finally:
			frappe.db.rollback(save_point=CHECK_SAVEPOINT)
			# DocType validation caches the unsaved meta (`setup_fields_to_fetch`).
			for doctype in (self.state.name, *self.state.children):
				clear_meta_cache(doctype)

	def child_errors(self) -> list[dict]:
		"""The first new child table's refusal, keyed to that child."""
		for doctype, child in self.state.children.items():
			try:
				validate(child.doc)
			except frappe.ValidationError as e:
				return [{**EditError(str(e)).as_dict(), "doctype": doctype}]
			child.doc.db_insert()
			# A Table MultiSelect's check reads the child's Link field from the database.
			for row in child.doc.get_all_children():
				row.name = row.name or frappe.generate_hash()
				row.db_insert()
		return []

	def parent_errors(self) -> list[dict]:
		validate(self.state.doc)
		return []

	def layout_errors(self) -> list[dict]:
		errors = []
		for type in sorted(self.state.touched):
			layouts = [layout for layout in self.state.layouts_of(type) if not layout.deleted]
			errors += [error for layout in layouts if (error := self.layout_error(layout))]
			defaults = [layout for layout in layouts if not layout.condition]
			if len(defaults) > 1:
				message = _("Only one {0} layout can have no condition. Add a condition to the others.")
				errors.append(
					EditError(message.format(_(type)), kind="layout", layout=defaults[-1].id).as_dict()
				)
		return errors + self.new_name_errors()

	def new_name_errors(self) -> list[dict]:
		"""A field the save adds or renames must not take a name a layout it leaves alone uses."""
		fieldnames = {field.fieldname for field in self.state.doc.fields}
		if not fieldnames - self.state.saved_fieldnames:
			return []
		self.state.load_every_layout()
		untouched = [
			layout
			for layout in self.state.all_layouts()
			if layout.type not in self.state.touched and not layout.deleted
		]
		return [
			error
			for layout in untouched
			if (error := self.keyed_error(layout, self.refuse_names_of_fields, self.refuse_inline_fields))
		]

	@cached_property
	def meta(self) -> Meta:
		"""The fields as this save leaves them."""
		return Meta(self.state.doc)

	def layout_error(self, layout: EditorLayout) -> dict | None:
		"""The Form Layout checks, with the fields as this save leaves them."""
		row = frappe.new_doc("Form Layout")
		row.update(
			{
				"dt": self.state.name,
				"type": layout.type,
				"title": layout.title,
				"condition": layout.condition,
				"layout": frappe.as_json(layout.tree.tabs),
				"omitted": frappe.as_json(layout.omitted),
			}
		)
		row.flags.meta = self.meta
		return self.keyed_error(
			layout, lambda _layout: row.validate_layout(), lambda _layout: row._validate_length()
		)

	def keyed_error(self, layout: EditorLayout, *checks) -> dict | None:
		try:
			for check in checks:
				check(layout)
		except frappe.ValidationError as e:
			return EditError(str(e), kind="layout", layout=layout.id).as_dict()

	def refuse_names_of_fields(self, layout: EditorLayout):
		fieldnames = {
			field.fieldname for field in self.state.doc.fields if field.fieldtype not in LAYOUT_BREAKS
		}
		for tab in layout.tree.tabs:
			refuse_field_name(_("Tab"), tab.get("name"), fieldnames, self.state.name)
			for section in tab["sections"]:
				refuse_field_name(_("Section"), section.get("name"), fieldnames, self.state.name)

	def refuse_inline_fields(self, layout: EditorLayout):
		for field in inline_fields(layout.tree.tabs):
			validate_inline_field(field, self.meta)


def validate(doc):
	"""The controller's checks, then the document checks a save runs that can fail on editor input."""
	# A saved child's validate adds its parent columns with a commit, which ends the check's savepoint.
	doc.add_child_table_fields = lambda: None
	try:
		doc.run_method("validate")
	finally:
		del doc.add_child_table_fields
	doc._validate_mandatory()
	for each in (doc, *doc.get_all_children()):
		each._validate_selects()
		each._validate_length()
