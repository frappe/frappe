# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.desk.doctype.form_layout.app_layout import content_hash, read_app_layouts
from frappe.desk.doctype.form_layout.form_layout import FORM_LAYOUT_TYPES
from frappe.desk.doctype_editor_customize import get_customizations
from frappe.desk.doctype_editor_layouts import get_editor_layouts
from frappe.model import core_doctypes_list
from frappe.model.meta import Meta
from frappe.modules.utils import get_module_app
from frappe.query_builder.functions import Count, NullIf

DESIGN = "design"
CUSTOMIZE = "customize"


@frappe.desk_v2_only
@frappe.whitelist(methods=["GET"])
def get_doctype_editor(doctype: str, mode: str | None = None) -> dict:
	"""The DocType editor's state in the mode the server picks; never cached, so `base_version` is fresh."""
	mode = editor_mode(doctype, mode)
	meta = frappe.get_meta(doctype)
	editor = {
		"doctype": doctype,
		"mode": mode,
		"modes": editor_modes(meta),
		"base_version": base_version(doctype),
		"custom": meta.custom,
		"module": meta.module,
		"app_title": app_title(meta),
		"record_count": record_count(meta),
		"value_counts": value_counts(meta),
		"layouts": get_editor_layouts(doctype, custom=mode == CUSTOMIZE),
	}
	editor.update(design_state(doctype) if mode == DESIGN else get_customizations(meta))
	return editor


def editor_mode(doctype: str, mode: str | None = None) -> str:
	"""The mode to open: `mode` when the user may open it, else Design before Customize. Raises 403."""
	if not frappe.db.exists("DocType", doctype):
		frappe.throw(_("DocType {0} not found").format(frappe.bold(doctype)), frappe.DoesNotExistError)
	modes = editor_modes(frappe.get_meta(doctype))
	if not modes or (mode and mode not in modes):
		frappe.throw(
			_("You are not permitted to open {0} in this mode.").format(frappe.bold(doctype)),
			frappe.PermissionError,
		)
	return mode or modes[0]


def editor_modes(meta: Meta) -> list[str]:
	modes = []
	if "System Manager" in frappe.get_roles() and (meta.custom or frappe.conf.developer_mode):
		modes.append(DESIGN)
	if is_customizable(meta) and frappe.has_permission("Customize Form", "write"):
		modes.append(CUSTOMIZE)
	return modes


def is_customizable(meta: Meta) -> bool:
	"""Customize Form's own refusals: core DocTypes, Singles and custom DocTypes."""
	return not (meta.custom or meta.issingle or meta.name in core_doctypes_list)


def base_version(doctype: str) -> str:
	"""A hash of what either mode's save rewrites; the save compares it to refuse a stale editor."""
	state = [frappe.db.get_value("DocType", doctype, "modified")]
	for table, column in (("Custom Field", "dt"), ("Property Setter", "doc_type"), ("Form Layout", "dt")):
		state.append(
			frappe.get_all(
				table, filters={column: doctype}, fields=["name", "modified"], order_by="name", as_list=True
			)
		)
	for type in FORM_LAYOUT_TYPES:
		app_layouts = read_app_layouts(doctype, type)
		state.append(app_layouts.version if app_layouts else None)
	return content_hash(frappe.as_json(state).encode())


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
