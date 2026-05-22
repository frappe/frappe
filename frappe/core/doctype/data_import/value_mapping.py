# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""Value mapping for Data Import: child-table storage and O(1) lookup during import."""

import frappe
from frappe import _
from frappe.utils import cint, cstr

INVALID_VALUES = ("", None)


def get_parent_field(df) -> str | None:
	if getattr(df, "is_child_table_field", False) and getattr(df, "child_table_df", None):
		return df.child_table_df.fieldname
	return None


def get_field_key(reference_doctype: str, fieldname: str, parent_field: str | None = None) -> str:
	if parent_field:
		return f"{reference_doctype}.{parent_field}.{fieldname}"
	return f"{reference_doctype}.{fieldname}"


def get_field_key_from_df(df, reference_doctype: str) -> str:
	return get_field_key(reference_doctype, df.fieldname, get_parent_field(df))


def build_lookup_from_mappings(
	mappings: list, reference_doctype: str | None = None
) -> dict[str, dict[str, str]]:
	lookup: dict[str, dict[str, str]] = {}
	for row in mappings:
		row = frappe._dict(row)
		ref = row.reference_doctype or reference_doctype or row.parenttype
		source, target = cstr(row.source_value), (row.target_value or "").strip()
		if not (ref and row.fieldname and source and target):
			continue
		key = get_field_key(ref, row.fieldname, row.parent_field or None)
		lookup.setdefault(key, {})[source] = target
	return lookup


def build_lookup_for_data_import(
	data_import_name: str | None, reference_doctype: str
) -> dict[str, dict[str, str]]:
	if not data_import_name or not frappe.db.exists("Data Import", data_import_name):
		return {}
	rows = frappe.get_all(
		"Data Import Value Mapping",
		filters={"parent": data_import_name},
		fields=["fieldname", "parent_field", "source_value", "target_value"],
	)
	return build_lookup_from_mappings(rows, reference_doctype)


def resolve_import_value(value, df, reference_doctype: str, lookup: dict) -> str:
	if value in INVALID_VALUES:
		return value
	return lookup.get(get_field_key_from_df(df, reference_doctype), {}).get(cstr(value), value)


def get_invalid_link_select_items(col) -> list[dict]:
	from frappe.core.doctype.data_import.importer import get_select_options, get_value_row_map

	if not col.df or col.skip_import or not any(col.column_values):
		return []

	value_rows = get_value_row_map(col.column_values, col.value_row_numbers)
	if col.df.fieldtype == "Link":
		transform = (lambda v: cstr(v).lower()) if frappe.db.db_type == "mariadb" else cstr
		exists = {
			transform(d.name)
			for d in frappe.get_all(
				col.df.options, filters={"name": ("in", list({transform(k) for k in value_rows}))}
			)
		}
		invalid_keys = [k for k in value_rows if transform(k) not in exists]
	elif col.df.fieldtype == "Select":
		options = get_select_options(col.df)
		if not options:
			return []
		invalid_keys = [k for k in value_rows if cstr(k).strip() not in options]
	else:
		return []

	return [{"source": k, "rows": value_rows[k]} for k in invalid_keys]


def get_unmapped_invalid_values_for_column(col, lookup: dict | None, reference_doctype: str) -> list[dict]:
	items = (
		col.invalid_value_items
		if getattr(col, "invalid_value_items", None) is not None
		else get_invalid_link_select_items(col)
	)
	field_map = (lookup or {}).get(get_field_key_from_df(col.df, reference_doctype), {})
	return [item for item in items if cstr(item["source"]) not in field_map]


def get_blocking_warnings(warnings: list, import_file) -> list:
	cols = {c.column_number: c for c in import_file.header.columns}
	blocking = []
	for warning in warnings:
		if warning.get("type") == "info":
			continue
		if warning.get("type") == "value_mapping":
			col = cols.get(cint(warning.get("col")))
			if col and get_unmapped_invalid_values_for_column(
				col, import_file.value_lookup, import_file.reference_doctype
			):
				blocking.append(warning)
			continue
		blocking.append(warning)
	return blocking


def get_mapping_hints(import_file, reference_doctype: str, lookup: dict) -> dict:
	from frappe.core.doctype.data_import.importer import get_select_options

	hints = {}
	for col in import_file.header.columns:
		if not col.df:
			continue
		items = (
			col.invalid_value_items
			if getattr(col, "invalid_value_items", None) is not None
			else get_invalid_link_select_items(col)
		)
		if not items:
			continue

		field_map = lookup.get(get_field_key_from_df(col.df, reference_doctype), {})
		parent_field = get_parent_field(col.df) or ""
		select_options = get_select_options(col.df) if col.df.fieldtype == "Select" else []

		hints[cstr(col.column_number)] = [
			{
				"column": col.column_number,
				"fieldname": col.df.fieldname,
				"parent_field": parent_field,
				"fieldtype": col.df.fieldtype,
				"link_doctype": col.df.options if col.df.fieldtype == "Link" else None,
				"select_options": select_options,
				"source_value": item["source"],
				"rows": item["rows"],
				"target_value": field_map.get(cstr(item["source"])),
			}
			for item in items
		]
	return hints


def warn_invalid_link_select_values(col) -> None:
	from frappe.core.doctype.data_import.importer import format_invalid_values_with_rows, get_select_options

	items = get_invalid_link_select_items(col)
	col.invalid_value_items = items
	if not items:
		return

	invalid_keys = [item["source"] for item in items]
	value_rows = {item["source"]: item["rows"] for item in items}
	if col.df.fieldtype == "Link":
		message = _("The following values do not exist for {0}: {1}").format(
			col.df.options, format_invalid_values_with_rows(value_rows, invalid_keys)
		)
	else:
		footer = _("Values must be one of {0}").format(
			", ".join(frappe.bold(o) for o in get_select_options(col.df))
		)
		message = _("The following values are invalid: {0}").format(
			format_invalid_values_with_rows(value_rows, invalid_keys, footer=footer)
		)

	col.warnings.append({"col": col.column_number, "message": message, "type": "value_mapping"})
