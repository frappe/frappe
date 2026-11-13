# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""A new DocType's first save from the editor: insert it, then save its layout and edits in Design mode."""

import frappe
from frappe import _
from frappe.desk.doctype.form_layout.form_layout import parse_layout
from frappe.desk.doctype_editor.design_state import EditorLayout
from frappe.desk.doctype_editor.errors import EditError
from frappe.desk.doctype_editor.save import DesignSave
from frappe.desk.doctype_editor.versions import base_version


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def create_doctype(definition: dict | str, layout: list | str | None, edits: list | dict | str) -> dict:
	"""`layout` is the Details tree; `edits` apply over it as in `save_doctype_editor`."""
	definition = frappe.parse_json(definition)
	check_create(definition)
	return DoctypeCreate(definition, frappe.parse_json(layout), frappe.parse_json(edits)).run()


def check_create(definition: dict):
	if "System Manager" not in frappe.get_roles():
		frappe.throw(_("Design mode needs the System Manager role."), frappe.PermissionError)
	if not definition.get("custom") and not frappe.conf.developer_mode:
		frappe.throw(_("Design mode on a standard DocType needs developer mode."), frappe.PermissionError)


class DoctypeCreate:
	def __init__(self, definition: dict, layout: list | None, edits: list | dict):
		self.definition = definition
		self.name = definition.get("name")
		self.layout = layout
		self.edits = edits

	def run(self) -> dict:
		if self.name and frappe.db.exists("DocType", self.name):
			return self.refused(_("A DocType named {0} already exists.").format(self.name))
		if error := self.insert():
			return self.refused(error)
		result = self.save()
		if not result["saved"]:
			remove_doctype(self.name)
		return {**result, "doctype": self.name}

	def insert(self) -> str | None:
		"""Its DDL commits, so a failure after it leaves a DocType to remove."""
		messages = len(frappe.local.message_log)
		try:
			frappe.get_doc({**self.definition, "doctype": "DocType"}).insert()
		except Exception as e:
			frappe.db.rollback()
			del frappe.local.message_log[messages:]
			if self.name:
				remove_doctype(self.name)
			if isinstance(e, frappe.ValidationError):
				return str(e) or _("The DocType was not created.")
			frappe.log_error(f"DocType editor create of {self.name}")
			return _("The DocType was not created.")

	def save(self) -> dict:
		save = DesignSave(self.name, base_version(self.name), self.edits)
		if self.layout:
			tabs = parse_layout(frappe.as_json(self.layout))
			save.state.layouts_of("Details").append(EditorLayout("Details", "Details", tabs))
			save.state.touched.add("Details")
		return save.run()

	def refused(self, message: str) -> dict:
		return {"saved": False, "doctype": self.name, "errors": [EditError(message).as_dict()]}


def remove_doctype(name: str):
	frappe.db.delete("Form Layout", {"dt": name})
	frappe.delete_doc("DocType", name, force=True, ignore_missing=True)
	frappe.db.sql_ddl(f"drop table if exists `tab{name}`")
