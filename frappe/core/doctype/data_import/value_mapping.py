# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""Value mapping for Data Import: child-table storage and O(1) lookup during import."""

import json

import frappe
from frappe import _
from frappe.utils import cint, cstr
from frappe.utils.data import escape_html

INVALID_VALUES = ("", None)


def get_parent_field(df) -> str | None:
	"""Return the child-table fieldname when ``df`` is a column inside a table field."""
	if getattr(df, "is_child_table_field", False) and getattr(df, "child_table_df", None):
		return df.child_table_df.fieldname
	return None


def get_field_key(reference_doctype: str, fieldname: str, parent_field: str | None = None) -> str:
	"""Build a stable lookup key: ``Doctype.field`` or ``Doctype.parent_table.field`` for child rows."""
	if parent_field:
		return f"{reference_doctype}.{parent_field}.{fieldname}"
	return f"{reference_doctype}.{fieldname}"


def get_field_key_from_df(df, reference_doctype: str) -> str:
	"""Field key for a mapped DocField, including child-table parent when applicable."""
	return get_field_key(reference_doctype, df.fieldname, get_parent_field(df))


def normalize_source_value(value) -> str:
	"""Strip whitespace so file values match mapping keys saved from the UI."""
	return cstr(value).strip()


def build_lookup_from_mappings(
	mappings: list, reference_doctype: str | None = None
) -> dict[str, dict[str, str]]:
	"""Build nested lookup ``{field_key: {source_value: target_value}}`` from child-table rows.

	Used at import time for O(1) per-cell remapping. Rows with empty source or target are skipped.
	Later rows for the same field + source overwrite earlier ones.
	"""
	lookup: dict[str, dict[str, str]] = {}
	for row in mappings:
		row = frappe._dict(row)
		# Resolve DocType: explicit on row, else caller default, else child-table parenttype.
		ref = row.reference_doctype or reference_doctype or row.parenttype
		source, target = normalize_source_value(row.source_value), (row.target_value or "").strip()
		# Ignore incomplete mappings — they must not block or remap anything.
		if not (ref and row.fieldname and source and target):
			continue
		key = get_field_key(ref, row.fieldname, row.parent_field or None)
		lookup.setdefault(key, {})[source] = target
	return lookup


def build_lookup_for_data_import(
	data_import_name: str | None, reference_doctype: str
) -> dict[str, dict[str, str]]:
	"""Load saved value mappings from the Data Import child table into a lookup dict."""
	if not data_import_name or not frappe.db.exists("Data Import", data_import_name):
		return {}
	rows = frappe.get_all(
		"Data Import Value Mapping",
		filters={"parent": data_import_name},
		fields=["fieldname", "parent_field", "source_value", "target_value"],
	)
	return build_lookup_from_mappings(rows, reference_doctype)


def get_skipped_row_numbers(data_import) -> set[int]:
	"""Return 1-based sheet row numbers marked to skip on the Data Import form."""
	if not data_import or not getattr(data_import, "name", None):
		return set()

	skipped_rows = getattr(data_import, "skipped_rows", None)
	if skipped_rows is None:
		rows = frappe.get_all(
			"Data Import Skipped Row",
			filters={"parent": data_import.name},
			pluck="row_number",
		)
		return {cint(r) for r in rows}

	return {cint(row.row_number) for row in skipped_rows}


def get_field_map(col, lookup: dict | None, reference_doctype: str) -> dict[str, str]:
	"""Source → target map for one column's field, or empty dict when none exist."""
	return (lookup or {}).get(get_field_key_from_df(col.df, reference_doctype), {})


def get_column_invalid_items(col) -> list[dict]:
	"""Invalid Link/Select cell values for a column; reuses validation cache when already computed."""
	items = getattr(col, "invalid_value_items", None)
	if items is not None:
		return items
	return get_invalid_link_select_items(col)


def resolve_import_value(value, df, reference_doctype: str, lookup: dict) -> str:
	"""Replace a file cell value with its mapped target during import; leave empty/unknown values unchanged."""
	if value in INVALID_VALUES:
		return value
	source = normalize_source_value(value)
	return lookup.get(get_field_key_from_df(df, reference_doctype), {}).get(source, value)


def get_invalid_link_select_items(col) -> list[dict]:
	"""Scan a column and return distinct invalid Link/Select values with 1-based sheet row numbers.

	Each item is ``{"source": <file value>, "rows": [2, 5, …]}``. Link checks are case-insensitive
	on MariaDB to match DB behaviour; Select checks use stripped values against field options.
	"""
	from frappe.core.doctype.data_import.importer import get_select_options, get_value_row_map

	if not col.df or col.skip_import or not any(col.column_values):
		return []

	# Group each distinct cell value with the sheet rows where it appears.
	value_rows = get_value_row_map(col.column_values, col.value_row_numbers)
	if col.df.fieldtype == "Link":
		# One DB query for all distinct values; MariaDB compares names case-insensitively.
		transform = (lambda v: cstr(v).lower()) if frappe.db.db_type == "mariadb" else cstr
		exists = {
			transform(d.name)
			for d in frappe.get_all(
				col.df.options, filters={"name": ("in", list({transform(k) for k in value_rows}))}
			)
		}
		import_refs = getattr(col, "import_refs", None)
		allow_same_file_parents = col.df.options == col.doctype and import_refs
		invalid_keys = []
		for key in value_rows:
			if transform(key) in exists:
				continue
			normalized_key = normalize_source_value(key)
			if allow_same_file_parents and normalized_key in import_refs:
				continue
			invalid_keys.append(key)
	elif col.df.fieldtype == "Select":
		options = get_select_options(col.df)
		if not options:
			return []
		invalid_keys = [k for k in value_rows if normalize_source_value(k) not in options]
	else:
		return []

	return [{"source": k, "rows": value_rows[k]} for k in invalid_keys]


def get_unmapped_invalid_values_for_column(
	col, lookup: dict | None, reference_doctype: str, skipped_rows: set[int] | None = None
) -> list[dict]:
	"""Invalid values in a column that still have no user-provided mapping — these block import."""
	field_map = get_field_map(col, lookup, reference_doctype)
	unmapped = [
		item
		for item in get_column_invalid_items(col)
		if normalize_source_value(item["source"]) not in field_map
	]
	if not skipped_rows:
		return unmapped
	return [item for item in unmapped if any(cint(row) not in skipped_rows for row in item["rows"])]


def get_blocking_warnings(warnings: list, import_file, data_import=None) -> list:
	"""Filter template warnings to those that should prevent import from starting.

	Info warnings are ignored. ``value_mapping`` warnings stay only while unmapped invalid values
	remain; fully mapped columns keep their warning for display but no longer block import.
	Row warnings for user-skipped rows are ignored.
	"""
	cols = {c.column_number: c for c in import_file.header.columns}
	skipped_rows = get_skipped_row_numbers(data_import)
	blocking = []
	for warning in warnings:
		if warning.get("type") == "info":
			continue
		if skipped_rows and warning.get("row") and cint(warning.get("row")) in skipped_rows:
			continue
		if warning.get("type") == "value_mapping":
			col = cols.get(cint(warning.get("col")))
			if col and get_unmapped_invalid_values_for_column(
				col, import_file.value_lookup, import_file.reference_doctype, skipped_rows
			):
				blocking.append(warning)
			continue
		blocking.append(warning)
	return blocking


def get_mapping_hints(import_file, reference_doctype: str, lookup: dict) -> dict:
	"""Build UI payload to populate the Value Mappings child table on the Data Import form.

	Returns ``{column_number: [hint, …]}`` where each hint carries field metadata, affected rows,
	and any already-saved ``target_value`` from the lookup.
	"""
	from frappe.core.doctype.data_import.importer import get_select_options

	hints = {}
	for col in import_file.header.columns:
		if not col.df:
			continue
		items = get_column_invalid_items(col)
		if not items:
			continue

		field_map = get_field_map(col, lookup, reference_doctype)
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
				"target_value": field_map.get(normalize_source_value(item["source"])),
			}
			for item in items
		]
	return hints


def warn_invalid_link_select_values(col) -> None:
	"""Append a column-level ``value_mapping`` warning listing invalid Link/Select values with row numbers."""
	from frappe.core.doctype.data_import.importer import format_row_numbers_for_warning, get_select_options

	items = get_invalid_link_select_items(col)
	col.invalid_value_items = items
	if not items:
		return

	lines = []
	options_string = None
	if col.df.fieldtype == "Select":
		select_options = get_select_options(col.df)
		if select_options:
			options_string = ", ".join(select_options)

	for item in items:
		source = escape_html(item["source"])
		rows_str = format_row_numbers_for_warning(item["rows"])
		row_label = (
			_("row {0}").format(rows_str) if len(item["rows"]) == 1 else _("rows {0}").format(rows_str)
		)

		if col.df.fieldtype == "Link":
			line = _('"{0}" is not a valid {1} — {2}').format(
				frappe.bold(source), frappe.bold(col.df.label), row_label
			)
		else:
			line = _('"{0}" is not valid — {1}').format(frappe.bold(source), row_label)
		lines.append(line)

	if col.df.fieldtype == "Select" and options_string and lines:
		allowed = _("Allowed: {0}").format(frappe.bold(options_string))
		lines[-1] = f"{lines[-1]} · {allowed}"

	message = "<br>".join(lines)
	col.warnings.append({"col": col.column_number, "message": message, "type": "value_mapping"})


def mapping_row_key(row) -> str:
	"""Stable key for a value-mapping row or preview hint."""
	return f"{row.get('column')}|{row.get('fieldname')}|{row.get('parent_field') or ''}|{row.get('source_value')}"


def no_of_rows_count(rows: list) -> str:
	"""Row count for the Value Mappings grid (actual row numbers live in ``row_numbers``)."""
	if not rows:
		return ""
	return cstr(len(rows))


def child_row_from_hint(item: dict, columns: dict) -> dict:
	"""Build a Value Mappings child-table row from a preview mapping hint."""
	item = frappe._dict(item)
	column_number = item.column
	col = columns.get(column_number)
	column_label = (col.header_title if col else None) or _("Column {0}").format(column_number)
	rows = item.rows or []
	select_options = item.select_options or []

	return {
		"column": column_number,
		"column_label": column_label,
		"fieldname": item.fieldname,
		"parent_field": item.parent_field or "",
		"fieldtype": item.fieldtype,
		"link_doctype": item.link_doctype,
		"select_options": "\n".join(select_options) if select_options else "",
		"source_value": item.source_value,
		"target_value": item.target_value or "",
		"row_numbers": json.dumps(rows),
		"no_of_rows": no_of_rows_count(rows),
	}


def sync_value_mappings(doc, import_file, lookup: dict | None = None) -> bool:
	"""Populate the Value Mappings child table from invalid Link/Select values in the import file.

	Preserves user-provided ``target_value`` entries for rows that still appear in the file.
	"""
	mapping_hints = get_mapping_hints(import_file, doc.reference_doctype, lookup or {})
	items = [item for hints in mapping_hints.values() for item in hints]
	columns = {col.column_number: col for col in import_file.header.columns}

	if not items:
		if doc.get("value_mappings"):
			doc.set("value_mappings", [])
			return True
		return False

	existing_targets = {
		mapping_row_key(row): (row.target_value or "").strip() for row in (doc.get("value_mappings") or [])
	}
	new_rows = []
	for item in items:
		key = mapping_row_key(item)
		data = child_row_from_hint(item, columns)
		target_value = existing_targets.get(key) or (item.get("target_value") or "")
		data["target_value"] = target_value
		new_rows.append(data)

	current_rows = [
		{
			"column": row.column,
			"fieldname": row.fieldname,
			"parent_field": row.parent_field or "",
			"source_value": row.source_value,
			"column_label": row.column_label,
			"fieldtype": row.fieldtype,
			"link_doctype": row.link_doctype,
			"select_options": row.select_options,
			"target_value": row.target_value or "",
			"row_numbers": row.row_numbers,
			"no_of_rows": row.no_of_rows,
		}
		for row in (doc.get("value_mappings") or [])
	]

	if new_rows == current_rows:
		return False

	doc.set("value_mappings", [])
	for row in new_rows:
		doc.append("value_mappings", row)
	return True
