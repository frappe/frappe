# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""Rename a saved field of a custom DocType: its data, reports and settings follow, and so do the layouts."""

import frappe
from frappe import _
from frappe.desk.doctype_editor.mode import check_mode
from frappe.desk.doctype_editor.save import DesignSave
from frappe.desk.doctype_editor.versions import base_version


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def rename_field(doctype: str, old_fieldname: str, new_fieldname: str) -> dict:
	check_mode(doctype, "Design")
	edit = {"act": "fields.rename_field", "fieldname": old_fieldname, "new_fieldname": new_fieldname}
	return DesignSave(doctype, base_version(doctype), [edit]).run()
