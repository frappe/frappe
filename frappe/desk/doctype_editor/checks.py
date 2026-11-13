# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""What a Design save checks before its first write: a DocType's DDL commits, so a later refusal cannot undo it."""

import frappe
from frappe import _
from frappe.desk.doctype.form_layout.form_layout import LAYOUT_BREAKS, refuse_field_name
from frappe.desk.doctype_editor.design_state import DesignState, EditorLayout
from frappe.desk.doctype_editor.errors import EditError

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
			for child in self.state.children.values():
				validate(child.doc)
				child.doc.db_insert()
			validate(self.state.doc)
		except frappe.ValidationError as e:
			return [EditError(str(e)).as_dict()]
		finally:
			frappe.db.rollback(save_point=CHECK_SAVEPOINT)
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
		return errors

	def layout_error(self, layout: EditorLayout) -> dict | None:
		"""The Form Layout checks, with the fields as this save leaves them."""
		row = frappe.new_doc("Form Layout")
		row.update(
			{
				"dt": self.state.name,
				"type": layout.type,
				"layout": frappe.as_json(layout.tree.tabs),
				"omitted": frappe.as_json(layout.omitted),
			}
		)
		try:
			row.validate_layout()
			self.refuse_names_of_fields(layout)
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


def validate(doc):
	"""The controller's checks, then the document checks a save runs that can fail on editor input."""
	doc.run_method("validate")
	doc._validate_mandatory()
	for each in (doc, *doc.get_all_children()):
		each._validate_selects()
		each._validate_length()
