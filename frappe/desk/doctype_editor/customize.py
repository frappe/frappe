# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.core.doctype.doctype.doctype import get_fields_not_allowed_in_list_view
from frappe.custom.doctype.customize_form.customize_form import (
	ALLOWED_FIELDTYPE_CHANGE,
	ALLOWED_OPTIONS_CHANGE,
	is_standard_or_system_generated_field,
)
from frappe.model.docfield import supports_translation
from frappe.model.meta import Meta

APP_ROW_TABLES = {"DocType Link": "links", "DocType Action": "actions", "DocType State": "states"}


def get_customizations(meta: Meta) -> dict:
	"""The site's changes to a standard DocType, and what Customize Form refuses to change."""
	app_doc = frappe.get_doc("DocType", meta.name)
	app_fields = {df.fieldname: df for df in app_doc.fields}
	standard = [df for df in meta.fields if is_standard_or_system_generated_field(df)]
	not_in_list_view = get_fields_not_allowed_in_list_view(meta)
	return {
		"definition": meta.as_dict(no_nulls=True),
		"custom_fields": frappe.get_all(
			"Custom Field",
			filters={"dt": meta.name},
			fields=[
				"name",
				"fieldname",
				"label",
				"fieldtype",
				"insert_after",
				"module",
				"is_system_generated",
			],
			order_by="creation",
		),
		"property_setters": property_setters(meta.name, app_doc, app_fields),
		"locks": {
			df.fieldname: field_locks(df, app_fields.get(df.fieldname), not_in_list_view) for df in standard
		},
		"fieldtype_changes": {df.fieldname: fieldtype_changes(df.fieldtype) for df in standard},
	}


def property_setters(doctype: str, app_doc, app_fields: dict) -> list[dict]:
	"""Each Property Setter with `app_value`, the value the app ships; None on a custom field or row."""
	rows = frappe.get_all(
		"Property Setter",
		filters={"doc_type": doctype},
		fields=[
			"name",
			"doctype_or_field",
			"field_name",
			"row_name",
			"property",
			"value",
			"property_type",
			"module",
			"is_system_generated",
		],
		order_by="creation",
	)
	for row in rows:
		owner = setter_owner(row, app_doc, app_fields)
		row.app_value = owner.get(row.property) if owner else None
	return rows


def setter_owner(row, app_doc, app_fields: dict):
	"""The app's DocType, field, link, action or state that a Property Setter row overrides."""
	if row.doctype_or_field == "DocType":
		return app_doc
	if table := APP_ROW_TABLES.get(row.doctype_or_field):
		return next((r for r in app_doc.get(table) if r.name == row.row_name and not r.custom), None)
	return app_fields.get(row.field_name)


def field_locks(df, app_field, not_in_list_view: list) -> dict[str, str]:
	"""Mirrors `CustomizeForm.check_property_change`: `property -> reason` for each refused change."""
	locks = {}
	if app_field and app_field.reqd:
		locks["reqd"] = _("The app makes this field mandatory.")
	if app_field and app_field.read_only:
		locks["read_only"] = _("The app makes this field read only.")
	if app_field and not app_field.allow_on_submit:
		locks["allow_on_submit"] = _("The app does not allow this field to change after submit.")
	if app_field and not app_field.is_virtual:
		locks["is_virtual"] = _("A standard field cannot become virtual.")
	if df.fieldtype not in ALLOWED_OPTIONS_CHANGE:
		locks["options"] = _("Options of a {0} field cannot be changed.").format(_(df.fieldtype))
	if not supports_translation(df.fieldtype):
		locks["translatable"] = _("A {0} field cannot be translated.").format(_(df.fieldtype))
	if df.fieldtype in not_in_list_view:
		locks["in_list_view"] = _("A {0} field cannot show in the list view.").format(_(df.fieldtype))
	if not fieldtype_changes(df.fieldtype):
		locks["fieldtype"] = _("A {0} field cannot change its type.").format(_(df.fieldtype))
	return locks


def fieldtype_changes(fieldtype: str) -> list[str]:
	"""The types Customize Form lets this type become."""
	return sorted(
		{other for group in ALLOWED_FIELDTYPE_CHANGE if fieldtype in group for other in group} - {fieldtype}
	)
