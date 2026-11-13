# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""The DocType editor's save in Customize mode: Design's save, written through Customize Form."""

import frappe
from frappe.custom.doctype.custom_field.custom_field import rename_fieldname
from frappe.custom.doctype.property_setter.property_setter import delete_property_setter
from frappe.desk.doctype.form_layout.form_layout import publish_doctype_update
from frappe.desk.doctype_editor.customize_checks import CustomizeChecks
from frappe.desk.doctype_editor.customize_edits import CustomizeEdits
from frappe.desk.doctype_editor.customize_state import CustomizeState
from frappe.desk.doctype_editor.save import DesignSave
from frappe.desk.doctype_editor.versions import changed_error, customizations_version, stale_error


class CustomizeSave(DesignSave):
	State, Edits, Checks = CustomizeState, CustomizeEdits, CustomizeChecks
	state: CustomizeState

	def run(self) -> dict:
		result = super().run()
		if result["saved"] and self.checks.skipped:
			result["skipped"] = self.checks.skipped
		return result

	def check(self):
		if error := self.customizations_stale() or self.reset_rows_stale():
			self.errors.insert(0, error)
		super().check()

	def customizations_stale(self) -> dict | None:
		if self.base_version.get("customizations") == customizations_version(self.doctype):
			return None
		return changed_error(*self.last_customization())

	def last_customization(self) -> tuple:
		rows = [
			*frappe.get_all("Custom Field", {"dt": self.doctype}, ["modified_by", "modified"]),
			*frappe.get_all("Property Setter", {"doc_type": self.doctype}, ["modified_by", "modified"]),
		]
		last = max(rows, key=lambda row: row.modified, default=None)
		return (last.modified_by, last.modified) if last else (frappe.session.user, frappe.utils.now())

	def reset_rows_stale(self) -> dict | None:
		return stale_error(self.doctype, self.base_version, self.state.reset_rows, [])

	def written_app_types(self) -> list[str]:
		return []

	def write(self) -> list[dict] | None:
		"""Customize Form's DDL commits, so a later failure reports what is already written."""
		self.written: list[str] = []
		messages = len(frappe.local.message_log)
		anchors = {**self.saved_anchors(), **self.state.anchors}
		try:
			for child in self.state.children.values():
				child.doc.insert()
				self.written.append(child.name)
			self.rename_custom_fields()
			self.state.doc.hide_success = True
			self.state.doc.save_customization()
			self.written.append(self.doctype)
			self.set_anchors(anchors)
			for fieldname, property in self.state.property_deletes:
				delete_property_setter(self.doctype, property, fieldname)
			for row in self.state.reset_rows:
				self.locked_row(row).delete()
			self.write_rows()
		except Exception as e:
			frappe.db.rollback()
			self.note_committed()
			return [self.failure(e)]
		finally:
			del frappe.local.message_log[messages:]
			if self.written:
				frappe.clear_cache(doctype=self.doctype)
				publish_doctype_update(self.doctype)

	def note_committed(self):
		"""`rename_fieldname` and Customize Form's DDL commit, so the rollback may leave them written."""
		committed = customizations_version(self.doctype) != self.base_version.get("customizations")
		if committed and self.doctype not in self.written:
			self.written.append(self.doctype)
		elif not committed and self.doctype in self.written:
			self.written.remove(self.doctype)

	def rename_custom_fields(self):
		for old, new in self.state.renames:
			rename_fieldname(self.custom_field_name(old), new)

	def saved_anchors(self) -> dict:
		"""Customize Form's save resets every custom field's `insert_after`; a container anchor is put back."""
		renamed = dict(self.state.renames)
		rows = frappe.get_all(
			"Custom Field", {"dt": self.doctype, "is_system_generated": 0}, ["fieldname", "insert_after"]
		)
		kept = {field.fieldname for field in self.state.doc.fields}
		deleted = {row.fieldname for row in rows} - kept - renamed.keys()
		anchors = {}
		for row in rows:
			anchor = renamed.get(row.insert_after, row.insert_after)
			if row.fieldname not in deleted and anchor not in deleted:
				anchors[renamed.get(row.fieldname, row.fieldname)] = anchor
		return anchors

	def set_anchors(self, anchors: dict):
		rows = frappe.get_all("Custom Field", {"dt": self.doctype}, ["name", "fieldname", "insert_after"])
		for row in rows:
			if row.fieldname in anchors and row.insert_after != anchors[row.fieldname]:
				frappe.db.set_value("Custom Field", row.name, "insert_after", anchors[row.fieldname])

	def custom_field_name(self, fieldname: str) -> str | None:
		return frappe.db.get_value("Custom Field", {"dt": self.doctype, "fieldname": fieldname})
