# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""Customize mode's immediate acts: Reset all customizations and Export customizations."""

import frappe
from frappe import _
from frappe.desk.doctype.form_layout.form_layout import publish_doctype_update
from frappe.desk.doctype_editor.mode import check_mode
from frappe.modules.utils import export_customizations


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def reset_all(doctype: str, confirm: bool = False) -> dict:
	"""Counts what a reset deletes and keeps; with `confirm`, deletes it. Rows that apps made stay."""
	check_mode(doctype, "Customize")
	delete, keep = customization_rows(doctype)
	counts = {"delete": {key: len(rows) for key, rows in delete.items()}}
	counts["keep"] = {key: len(rows) for key, rows in keep.items()}
	if frappe.utils.sbool(confirm):
		for key, rows in delete.items():
			for name in rows:
				frappe.delete_doc(RESET_DOCTYPES[key], name, ignore_permissions=True)
		frappe.clear_cache(doctype=doctype)
		publish_doctype_update(doctype)
	return counts


@frappe.desk_v2_only
@frappe.whitelist(methods=["POST"])
def export(
	doctype: str, module: str, sync_on_migrate: bool = False, with_permissions: bool = False
) -> str | None:
	check_mode(doctype, "Customize")
	if not frappe.conf.developer_mode:
		frappe.throw(_("Export of customizations needs developer mode."), frappe.PermissionError)
	return export_customizations(
		module, doctype, frappe.utils.sbool(sync_on_migrate), frappe.utils.sbool(with_permissions)
	)


RESET_DOCTYPES = {
	"custom_fields": "Custom Field",
	"property_setters": "Property Setter",
	"layouts": "Form Layout",
}


def customization_rows(doctype: str) -> tuple[dict, dict]:
	"""Like desk v1's reset, a naming series' options stay; so do fields only Administrator may delete."""
	fields = frappe.get_all(
		"Custom Field", {"dt": doctype}, ["name", "is_system_generated", "owner"], order_by="creation"
	)
	setters = frappe.get_all(
		"Property Setter",
		{"doc_type": doctype},
		["name", "is_system_generated", "field_name", "property"],
		order_by="creation",
	)
	layouts = frappe.get_all("Form Layout", {"dt": doctype}, ["name", "app"], order_by="creation")
	kept = {
		"custom_fields": [row.name for row in fields if row.is_system_generated or admin_only(row)],
		"property_setters": [row.name for row in setters if row.is_system_generated or is_series(row)],
		"layouts": [row.name for row in layouts if row.app],
	}
	every = {"custom_fields": fields, "property_setters": setters, "layouts": layouts}
	deleted = {key: [row.name for row in rows if row.name not in kept[key]] for key, rows in every.items()}
	return deleted, kept


def is_series(setter) -> bool:
	return setter.field_name == "naming_series" and setter.property == "options"


def admin_only(field) -> bool:
	return field.owner == "Administrator" and frappe.session.user != "Administrator"
