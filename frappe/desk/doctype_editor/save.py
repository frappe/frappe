# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""The DocType editor's save in Design mode: apply the edits, check everything, then write."""

import frappe
from frappe import _
from frappe.desk.doctype.form_layout.form_layout import (
	OMITTING_LAYOUT_TYPES,
	publish_doctype_update,
	write_layout_row,
)
from frappe.desk.doctype_editor.checks import DesignChecks
from frappe.desk.doctype_editor.design_edits import DesignEdits
from frappe.desk.doctype_editor.design_state import DesignState
from frappe.desk.doctype_editor.errors import EditError, StaleWrite
from frappe.desk.doctype_editor.mode import check_mode
from frappe.desk.doctype_editor.versions import base_version as current_version
from frappe.desk.doctype_editor.versions import changed_error, stale_error
from frappe.model import table_fields
from frappe.model.utils.rename_field import (
	rename_field,
	update_property_setters,
	update_user_settings,
)


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def save_doctype_editor(doctype: str, mode: str, base_version: dict | str, edits: list | dict) -> dict:
	check_mode(doctype, mode)
	# CustomizeSave subclasses DesignSave, so it imports this module.
	from frappe.desk.doctype_editor.customize_save import CustomizeSave

	save = CustomizeSave if mode == "Customize" else DesignSave
	return save(doctype, frappe.parse_json(base_version), frappe.parse_json(edits)).run()


WRITE_SAVEPOINT = "doctype_editor_write"


class DesignSave:
	State, Edits, Checks = DesignState, DesignEdits, DesignChecks

	def __init__(self, doctype: str, base_version: dict, edits: list | dict):
		"""`edits` is the parent's list, or `{doctype: [edits]}` for the parent and the child tables it adds."""
		self.doctype = doctype
		self.base_version = base_version
		self.edits = edits if isinstance(edits, dict) else {doctype: edits}
		self.state = self.State(doctype)
		self.errors: list[dict] = []

	def run(self) -> dict:
		self.apply_edits()
		self.check()
		if self.errors:
			return {"saved": False, "errors": self.errors}
		parents = self.parents_modified()
		if errors := self.write():
			return {"saved": False, "written": self.written, "errors": errors}
		return {
			"saved": True,
			"base_version": current_version(self.doctype),
			"children": list(self.state.children),
			"parents": self.moved_parents(parents),
		}

	def parents_modified(self) -> dict[str, str]:
		"""A child table's save moves its parents' `modified` (`change_modified_of_parent`)."""
		if not self.state.doc.istable:
			return {}
		parents = frappe.get_all(
			"DocField",
			filters={"fieldtype": ["in", table_fields], "options": self.doctype, "parenttype": "DocType"},
			pluck="parent",
			distinct=True,
		)
		return parent_versions(parents)

	def moved_parents(self, before: dict[str, str]) -> dict[str, dict]:
		"""Each parent's `modified` before and after, so its editor's next save is not refused as stale."""
		after = parent_versions(list(before))
		return {
			name: {"was": was, "now": after[name]}
			for name, was in before.items()
			if after.get(name, was) != was
		}

	def apply_edits(self):
		self.apply(self.state, self.edits.get(self.doctype) or [])
		self.drop_unnamed_children()
		for doctype, edits in self.edits.items():
			if doctype == self.doctype:
				continue
			if child := self.state.children.get(doctype):
				self.apply(child, edits, doctype)
			else:
				message = _("{0} is not a child table this save adds.").format(doctype)
				self.errors.append({**EditError(message).as_dict(), "doctype": doctype})

	def drop_unnamed_children(self):
		"""A new child table that no Table field names after a later edit is not inserted."""
		named = {field.options for field in self.state.doc.fields if field.fieldtype in table_fields}
		self.state.children = {name: child for name, child in self.state.children.items() if name in named}

	def apply(self, state: DesignState, edits: list, doctype: str | None = None):
		# A child table this save adds is a new DocType, so it takes Design's edits in either mode.
		applier = DesignEdits(state) if doctype else self.Edits(state)
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
			self.checks = self.Checks(self.state)
			self.errors = self.checks.errors()

	def written_app_types(self) -> list[str]:
		return sorted(self.state.touched) if self.state.standard else []

	def write(self) -> list[dict] | None:
		"""Write in order; a DocType's DDL commits, so a later failure reports what is already written."""
		self.written: list[str] = []
		self.loaded_modified = self.state.doc.modified
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
		if isinstance(e, StaleWrite):
			return e.error
		if isinstance(e, frappe.ValidationError):
			return EditError(str(e) or _("The save failed.")).as_dict()
		frappe.log_error(f"DocType editor save of {self.doctype}")
		return EditError(_("The save failed.")).as_dict()

	def move_renamed_data(self):
		for old, new in self.state.renames:
			move_field_data(self.doctype, old, new)

	def roll_back(self) -> list[dict]:
		"""A DocType's DDL commits and drops the savepoint; the full rollback then undoes the data move."""
		try:
			frappe.db.rollback(save_point=WRITE_SAVEPOINT)
			self.written = []
		except Exception:
			frappe.db.rollback()
			if self.doctype not in self.written and self.doctype_committed():
				self.written.append(self.doctype)
			if self.doctype in self.written:
				return self.move_renamed_data_again()
		return []

	def doctype_committed(self) -> bool:
		"""Its save can fail after its DDL committed the DocType's rows."""
		modified = frappe.db.get_value("DocType", self.doctype, "modified")
		return str(modified) != str(self.loaded_modified)

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
			doc = self.locked_row(layout.row) if layout.row else frappe.new_doc("Form Layout")
			if layout.deleted:
				if layout.row:
					doc.delete()
				continue
			values = {
				"dt": self.doctype,
				"type": layout.type,
				"title": layout.title,
				"condition": layout.condition,
				"layout": frappe.as_json(layout.tree.tabs),
			}
			# A Details or New Record row's save computes it from the layout.
			if layout.type not in OMITTING_LAYOUT_TYPES:
				values["omitted"] = frappe.as_json(layout.omitted) if layout.omitted else None
			write_layout_row(doc, **values)

	def locked_row(self, name: str):
		"""The DocType's save ran since the stale check, so compare again under the row's lock."""
		doc = frappe.get_doc("Form Layout", name, for_update=True)
		if str(doc.modified) != (self.base_version.get("layouts") or {}).get(str(name)):
			raise StaleWrite(changed_error(doc.modified_by, doc.modified))
		return doc


def move_field_data(doctype: str, old: str, new: str):
	"""The util moves a table's rows of every parent; a value field it checks for a column first."""
	field = frappe.get_meta(doctype, cached=False).get_field(new)
	if not field or field.fieldtype not in table_fields:
		rename_field(doctype, old, new)
		return
	move_table_rows(doctype, field.options, old, new)
	update_property_setters(doctype, old, new)
	update_user_settings(doctype, old, new)


def move_table_rows(doctype: str, child_doctype: str, old: str, new: str):
	child = frappe.qb.DocType(child_doctype)
	frappe.qb.update(child).set(child.parentfield, new).where(
		(child.parenttype == doctype) & (child.parentfield == old)
	).run()


def parent_versions(doctypes: list[str]) -> dict[str, str]:
	if not doctypes:
		return {}
	rows = frappe.get_all("DocType", filters={"name": ["in", doctypes]}, fields=["name", "modified"])
	return {row.name: str(row.modified) for row in rows}
