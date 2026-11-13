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

RECORDS = "__records"


@frappe.desk_v2_only
@frappe.whitelist(methods=["GET"])
def get_doctype_editor(doctype: str, mode: str | None = None) -> dict:
	"""The DocType editor's state in the mode the server picks; never cached, so `base_version` is fresh."""
	modes = permitted_modes(doctype)
	mode = open_mode(doctype, mode, modes)
	meta = frappe.get_meta(doctype)
	records, values = readable_counts(meta)
	editor = {
		"doctype": doctype,
		"mode": mode,
		"modes": modes,
		"base_version": base_version(doctype),
		"custom": meta.custom,
		"module": meta.module,
		"app_title": app_title(meta),
		"record_count": records,
		"value_counts": values,
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


def readable_counts(meta: Meta) -> tuple[int | None, dict[str, int]]:
	"""How many records the user reads, and how many of them hold a value in each field the user reads."""
	if meta.issingle or meta.is_virtual:
		return None, {}
	parents = readable_parents(meta)
	if not parents:
		return None, {}
	fields = readable_fields(meta, parents)
	counts = [scope_counts(meta, parent, fields) for parent in parents]
	records = sum(count.pop(RECORDS) for count in counts)
	return records, {df.fieldname: sum(count[df.fieldname] for count in counts) for df in fields}


def readable_parents(meta: Meta) -> list[str | None]:
	"""`[None]` when the user reads the DocType; for a child table, the parents the user reads."""
	if not meta.istable:
		return [None] if frappe.has_permission(meta.name, "read") else []
	table_field = {"options": meta.name, "fieldtype": ["in", table_fields]}
	parents = {
		*frappe.get_all("DocField", filters={**table_field, "parenttype": "DocType"}, pluck="parent"),
		*frappe.get_all("Custom Field", filters=table_field, pluck="dt"),
	}
	return [parent for parent in sorted(parents) if frappe.has_permission(parent, "read")]


def readable_fields(meta: Meta, parents: list[str | None]) -> list:
	"""Data columns whose permlevel the user reads through every counted parent."""
	columns = set(frappe.db.get_table_columns(meta.name))
	permitted = [set(meta.get_permitted_fieldnames(parenttype=parent)) for parent in parents]
	return [
		df
		for df in meta.get_fieldnames_with_value(with_field_meta=True)
		if df.fieldname in columns and all(df.fieldname in fieldnames for fieldnames in permitted)
	]


def scope_counts(meta: Meta, parent: str | None, fields: list) -> dict[str, int]:
	"""Counts in one SELECT over the rows the user reads, under `parent` for a child table."""
	table = frappe.qb.DocType(meta.name)
	counts = [Count("*").as_(RECORDS)]
	counts += [Count(counted_value(table[df.fieldname], df.fieldtype)).as_(df.fieldname) for df in fields]
	return frappe.qb.get_query(
		meta.name,
		fields=counts,
		filters={"parenttype": parent} if parent else None,
		parent_doctype=parent,
		ignore_permissions=False,
	).run(as_dict=True)[0]


def counted_value(column, fieldtype: str):
	"""An empty string counts as no value; Postgres refuses to compare `''` with a number or a date."""
	db_type = frappe.db.type_map.get(fieldtype, ("",))[0]
	return NullIf(column, "") if "char" in db_type or "text" in db_type else column
