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
from frappe.desk.doctype_editor.design_edits import DesignEdits
from frappe.desk.doctype_editor.design_state import DesignState
from frappe.desk.doctype_editor.errors import EditError
from frappe.desk.doctype_editor.mode import check_mode
from frappe.desk.doctype_editor.versions import base_version as current_version
from frappe.desk.doctype_editor.versions import stale_error


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def save_doctype_editor(doctype: str, mode: str, base_version: dict | str, edits: list | dict) -> dict:
	check_mode(doctype, mode)
	if mode != "Design":
		frappe.throw(_("The Customize save is not built yet."))
	return DesignSave(doctype, frappe.parse_json(base_version), frappe.parse_json(edits)).run()


class DesignSave:
	def __init__(self, doctype: str, base_version: dict, edits: list):
		self.doctype = doctype
		self.base_version = base_version
		self.edits = edits
		self.state = DesignState(doctype)
		self.errors: list[dict] = []

	def run(self) -> dict:
		self.apply_edits()
		self.check()
		if self.errors:
			return {"saved": False, "errors": self.errors}
		self.write()
		return {"saved": True, "base_version": current_version(self.doctype)}

	def apply_edits(self):
		applier = DesignEdits(self.state)
		for index, edit in enumerate(self.edits):
			try:
				applier.apply(edit)
			except EditError as e:
				self.errors.append(e.as_dict(index))

	def check(self):
		rows = [layout.row for layout in self.state.all_layouts() if layout.row and layout.type in self.state.touched]
		if stale := stale_error(self.doctype, self.base_version, rows, self.written_app_types()):
			self.errors.insert(0, stale)

	def written_app_types(self) -> list[str]:
		return sorted(self.state.touched) if self.state.standard else []

	def write(self):
		self.state.doc.save()
		self.write_layouts()
		publish_doctype_update(self.doctype)

	def write_layouts(self):
		for layout in self.state.all_layouts():
			if layout.type not in self.state.touched:
				continue
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
			if doc.is_new():
				doc.fingerprint = source_fingerprint(self.doctype, layout.type)
			doc.flags.writes_omitted = layout.type in OMITTING_LAYOUT_TYPES
			if not doc.flags.writes_omitted:
				doc.omitted = frappe.as_json(layout.omitted) if layout.omitted else None
			doc.save()
