# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.desk.doctype_editor.customize import get_customizations
from frappe.desk.doctype_editor.layouts import get_editor_layouts
from frappe.desk.doctype_editor.mode import MODES, check_mode, mode_refusal
from frappe.desk.doctype_editor.versions import base_version
from frappe.model import table_fields
from frappe.model.meta import Meta
from frappe.modules.utils import get_module_app
from frappe.query_builder.functions import Count, NullIf


@frappe.desk_v2_only
@frappe.whitelist(methods=["GET"])
def get_doctype_editor(doctype: str, mode: str | None = None) -> dict:
	"""The DocType editor's state in the mode the server picks; never cached, so `base_version` is fresh."""
	modes = permitted_modes(doctype)
	mode = open_mode(doctype, mode, modes)
	meta = frappe.get_meta(doctype)
	counted = may_count(meta)
	editor = {
		"doctype": doctype,
		"mode": mode,
		"modes": modes,
		"base_version": base_version(doctype),
		"custom": meta.custom,
		"module": meta.module,
		"app_title": app_title(meta),
		"record_count": record_count(meta) if counted else None,
		"value_counts": value_counts(meta) if counted else {},
		"layouts": get_editor_layouts(doctype, custom=mode == "Customize"),
	}
	editor.update(design_state(doctype) if mode == "Design" else get_customizations(meta))
	return editor


def permitted_modes(doctype: str) -> list[str]:
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("DocType {0} not found").format(frappe.bold(doctype)), frappe.DoesNotExistError)
	return [mode for mode in MODES if not mode_refusal(doctype, mode)]


def open_mode(doctype: str, mode: str | None, modes: list[str]) -> str:
	"""`mode` when the user may open it, else the first permitted one. Raises 403."""
	if mode:
		check_mode(doctype, mode)
		return mode
	if not modes:
		frappe.throw(mode_refusal(doctype, MODES[0]), frappe.PermissionError)
	return modes[0]


def design_state(doctype: str) -> dict:
	"""The DocType as the app ships it: site custom fields are left out and only counted."""
	return {
		"definition": frappe.get_doc("DocType", doctype).as_dict(no_nulls=True),
		"site_custom_fields": frappe.db.count("Custom Field", {"dt": doctype}),
	}


def app_title(meta: Meta) -> str | None:
	if meta.custom:
		return None
	app = get_module_app(meta.module)
	return (frappe.get_hooks("app_title", app_name=app) or [app])[0]


def may_count(meta: Meta) -> bool:
	"""Counts are record data: the user reads the DocType, or for a child table one of its parents."""
	if not meta.istable:
		return frappe.has_permission(meta.name, "read")
	table_field = {"options": meta.name, "fieldtype": ["in", table_fields]}
	parents = {
		*frappe.get_all("DocField", filters={**table_field, "parenttype": "DocType"}, pluck="parent"),
		*frappe.get_all("Custom Field", filters=table_field, pluck="dt"),
	}
	return any(frappe.has_permission(parent, "read") for parent in parents)


def record_count(meta: Meta) -> int | None:
	if meta.issingle or meta.is_virtual:
		return None
	return frappe.db.count(meta.name)


def value_counts(meta: Meta) -> dict[str, int]:
	"""How many records hold a value in each data column, in one SELECT."""
	if meta.issingle or meta.is_virtual:
		return {}
	columns = set(frappe.db.get_table_columns(meta.name))
	fields = [df for df in meta.get_fieldnames_with_value(with_field_meta=True) if df.fieldname in columns]
	if not fields:
		return {}
	table = frappe.qb.DocType(meta.name)
	counts = [Count(counted_value(table[df.fieldname], df.fieldtype)).as_(df.fieldname) for df in fields]
	return frappe.qb.from_(table).select(*counts).run(as_dict=True)[0]


def counted_value(column, fieldtype: str):
	"""An empty string counts as no value; Postgres refuses to compare `''` with a number or a date."""
	db_type = frappe.db.type_map.get(fieldtype, ("",))[0]
	return NullIf(column, "") if "char" in db_type or "text" in db_type else column
