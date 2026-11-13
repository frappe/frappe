# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""A new DocType's first save from the editor: insert it, then save its layout and edits in Design mode."""

import frappe
from frappe import _
from frappe.core.doctype.doctype.doctype import START_WITH_LETTERS_PATTERN, WHITESPACE_PADDING_PATTERN
from frappe.desk.doctype.form_layout.form_layout import parse_layout
from frappe.desk.doctype_editor.design_state import EditorLayout
from frappe.desk.doctype_editor.errors import EditError
from frappe.desk.doctype_editor.mode import design_refusal
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
	if not isinstance(definition, dict):
		frappe.throw(_("The DocType definition must be an object."))
	if refusal := design_refusal(definition.get("custom")):
		frappe.throw(refusal, frappe.PermissionError)
	name = definition.get("name")
	# The name reaches DDL in remove_doctype: refuse anything a table name could not be.
	if (
		not isinstance(name, str)
		or WHITESPACE_PADDING_PATTERN.search(name)
		or not START_WITH_LETTERS_PATTERN.match(name)
	):
		frappe.throw(_("{0} is not a valid DocType name.").format(frappe.bold(str(name))), frappe.NameError)


class DoctypeCreate:
	def __init__(self, definition: dict, layout: list | None, edits: list | dict):
		self.definition = definition
		self.name = definition.get("name")
		self.layout = layout
		self.edits = edits

	def run(self) -> dict:
		if frappe.db.exists("DocType", self.name):
			return self.refused(_("A DocType named {0} already exists.").format(self.name))
		if error := self.insert():
			return self.refused(error)
		result = self.save()
		if result["saved"]:
			return {**result, "doctype": self.name}
		for name in {*result.pop("written", []), self.name}:
			remove_doctype(name)
		return {**result, "doctype": self.name}

	def insert(self) -> str | None:
		"""Its DDL commits, so a failure after it leaves a DocType to remove."""
		messages = len(frappe.local.message_log)
		try:
			frappe.get_doc({**self.definition, "doctype": "DocType"}).insert()
		except Exception as e:
			frappe.db.rollback()
			del frappe.local.message_log[messages:]
			# Another request created this name first: its DocType is not ours to remove.
			if not isinstance(e, frappe.DuplicateEntryError):
				remove_doctype(self.name)
			if not isinstance(e, frappe.ValidationError | frappe.NameError):
				raise
			return str(e) or _("The DocType was not created.")

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
	for layout in frappe.get_all("Form Layout", {"dt": name}, pluck="name"):
		frappe.delete_doc("Form Layout", layout, force=True, ignore_permissions=True)
	frappe.delete_doc("DocType", name, force=True, ignore_missing=True)
	frappe.db.sql_ddl(f"drop table if exists `tab{name}`")
