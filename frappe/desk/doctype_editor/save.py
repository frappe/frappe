# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""The DocType editor's save in Design mode: apply the edits, check everything, then write (#45866)."""

import frappe
from frappe import _
from frappe.desk.doctype.form_layout.form_layout import (
	OMITTING_LAYOUT_TYPES,
	publish_doctype_update,
	source_fingerprint,
)
from frappe.desk.doctype_editor.checks import DesignChecks
from frappe.desk.doctype_editor.design_edits import DesignEdits
from frappe.desk.doctype_editor.design_state import DesignState
from frappe.desk.doctype_editor.errors import EditError
from frappe.desk.doctype_editor.mode import check_mode
from frappe.desk.doctype_editor.versions import base_version as current_version
from frappe.desk.doctype_editor.versions import stale_error
from frappe.model.utils.rename_field import rename_field


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def save_doctype_editor(doctype: str, mode: str, base_version: dict | str, edits: list | dict) -> dict:
	check_mode(doctype, mode)
	if mode != "Design":
		frappe.throw(_("The Customize save is not built yet."))
	return DesignSave(doctype, frappe.parse_json(base_version), frappe.parse_json(edits)).run()


WRITE_SAVEPOINT = "doctype_editor_write"


class DesignSave:
	def __init__(self, doctype: str, base_version: dict, edits: list | dict):
		"""`edits` is the parent's list, or `{doctype: [edits]}` for the parent and the child tables it adds."""
		self.doctype = doctype
		self.base_version = base_version
		self.edits = edits if isinstance(edits, dict) else {doctype: edits}
		self.state = DesignState(doctype)
		self.errors: list[dict] = []

	def run(self) -> dict:
		self.apply_edits()
		self.check()
		if self.errors:
			return {"saved": False, "errors": self.errors}
		if errors := self.write():
			return {"saved": False, "written": self.written, "errors": errors}
		return {
			"saved": True,
			"base_version": current_version(self.doctype),
			"children": list(self.state.children),
		}

	def apply_edits(self):
		self.apply(self.state, self.edits.get(self.doctype) or [])
		for doctype, edits in self.edits.items():
			if doctype == self.doctype:
				continue
			if child := self.state.children.get(doctype):
				self.apply(child, edits, doctype)
			else:
				message = _("{0} is not a child table this save adds.").format(doctype)
				self.errors.append({**EditError(message).as_dict(), "doctype": doctype})

	def apply(self, state: DesignState, edits: list, doctype: str | None = None):
		applier = DesignEdits(state)
		for index, edit in enumerate(edits):
			try:
				applier.apply(edit)
			except EditError as e:
				self.add_error(e, index, doctype)
			except (TypeError, ValueError, KeyError, AttributeError, IndexError):
				self.add_error(EditError(_("This edit is malformed.")), index, doctype)

	def add_error(self, e: EditError, index: int, doctype: str | None):
		error = e.as_dict(index)
		self.errors.append({**error, "doctype": doctype} if doctype else error)

	def check(self):
		rows = [
			layout.row
			for layout in self.state.all_layouts()
			if layout.row and layout.type in self.state.touched
		]
		if stale := stale_error(self.doctype, self.base_version, rows, self.written_app_types()):
			self.errors.insert(0, stale)
		if not self.errors:
			self.errors = DesignChecks(self.state).errors()

	def written_app_types(self) -> list[str]:
		return sorted(self.state.touched) if self.state.standard else []

	def write(self) -> list[dict] | None:
		"""Write in order; a DocType's DDL commits, so a later failure reports what is already written."""
		self.written: list[str] = []
		messages = len(frappe.local.message_log)
		frappe.db.savepoint(WRITE_SAVEPOINT)
		try:
			for child in self.state.children.values():
				child.doc.insert()
				self.written.append(child.name)
			if self.state.standard:
				self.stage_app_layouts()
			self.state.doc.save()
			self.written.append(self.doctype)
			self.move_renamed_data()
			if not self.state.standard:
				self.write_rows()
		except Exception as e:
			error = self.failure(e)
			errors = [error, *self.roll_back()]
			del frappe.local.message_log[messages:]
			if self.written:
				publish_doctype_update(self.doctype)
			return errors
		publish_doctype_update(self.doctype)

	def failure(self, e: Exception) -> dict:
		if isinstance(e, frappe.ValidationError):
			return EditError(str(e) or _("The save failed.")).as_dict()
		frappe.log_error(f"DocType editor save of {self.doctype}")
		return EditError(_("The save failed.")).as_dict()

	def move_renamed_data(self):
		"""Unvalidated: a table field has no column of its own to check, only its rows' parentfield."""
		for old, new in self.state.renames:
			rename_field(self.doctype, old, new, validate=False)

	def roll_back(self) -> list[dict]:
		"""A DocType's DDL commits and drops the savepoint; the full rollback then undoes the data move."""
		try:
			frappe.db.rollback(save_point=WRITE_SAVEPOINT)
			self.written = []
		except Exception:
			frappe.db.rollback()
			if self.doctype in self.written:
				return self.move_renamed_data_again()
		return []

	def move_renamed_data_again(self) -> list[dict]:
		try:
			self.move_renamed_data()
		except Exception:
			frappe.db.rollback()
			frappe.log_error(f"DocType editor data move of {self.doctype}")
			return [EditError(_("The data of the renamed fields was not moved.")).as_dict()]
		return []

	def stage_app_layouts(self):
		"""The DocType's export writes these after its own files (`export_app_layouts`)."""
		self.state.doc.flags.app_layouts = {
			type: [layout.as_entry() for layout in self.state.layouts_of(type) if not layout.deleted]
			for type in self.state.touched
		}

	def write_rows(self):
		touched = [layout for layout in self.state.all_layouts() if layout.type in self.state.touched]
		# A row's save refuses a second default, so the old default gets its condition first.
		for layout in sorted(touched, key=lambda layout: (not layout.deleted, not layout.condition)):
			doc = frappe.get_doc("Form Layout", layout.row) if layout.row else frappe.new_doc("Form Layout")
			if layout.deleted:
				if layout.row:
					doc.delete()
				continue
			doc.update(
				{
					"dt": self.doctype,
					"type": layout.type,
					"title": layout.title,
					"condition": layout.condition,
					"layout": frappe.as_json(layout.tree.tabs),
				}
			)
			doc.fingerprint = source_fingerprint(self.doctype, layout.type)
			doc.flags.writes_omitted = layout.type in OMITTING_LAYOUT_TYPES
			if not doc.flags.writes_omitted:
				doc.omitted = frappe.as_json(layout.omitted) if layout.omitted else None
			doc.save()
