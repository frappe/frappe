# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.model import no_value_fields
from frappe.utils import cint, flt

ASSUMED_BODY_WIDTH_PX = 750
DEFAULT_COLUMN_WIDTH_PCT = 10
MAX_DEFAULT_TABLE_COLUMNS = 8
# classic wrapped text and table blocks in `padding: 10px 0px`; the beta renderer
# has no such default, so converted sections carry the gap explicitly
CONVERTED_SECTION_GAP_PX = 10
MARGIN_FIELDS = ("margin_top", "margin_bottom", "margin_left", "margin_right")
NUMERIC_DEFAULT_FIELDS = ("font_size", *MARGIN_FIELDS)
CONVERTED_FIELDS = ("pdf_generator", "page_number", *NUMERIC_DEFAULT_FIELDS)
CONVERSION_VALUE_FIELDS = (
	"classic_format_data",
	"print_format_builder",
	"print_format_builder_beta",
	*CONVERTED_FIELDS,
)

DEFAULT_PRINT_HEADING = (
	'{%- set heading = doc.get("select_print_heading") or doc.get("print_heading") or doc.doctype -%}'
	'{%- set sub_heading = doc.get("sub_heading") or doc.name -%}'
	'<div class="print-heading"><h2><div>{{ _(heading) }}</div>'
	'<small class="sub-heading">{{ _(sub_heading|string) }}</small></h2></div>'
)


def renders_from_file(doc) -> bool:
	"""Whether the format prints from an HTML file shipped in its module.

	`printview.get_print_format` reads that file and ignores the row's own
	`html`, so the builder has nothing to edit and must not offer to."""
	import os

	from frappe.modules import get_module_path, scrub

	if doc.get("standard") != "Yes" or doc.get("custom_format") or doc.get("raw_printing"):
		return False
	module = doc.get("module") or frappe.db.get_value("DocType", doc.get("doc_type"), "module")
	if not module or frappe.get_cached_value("Module Def", module, "custom"):
		return False
	try:
		path = os.path.join(get_module_path(module, "Print Format", doc.name), scrub(doc.name) + ".html")
	except (frappe.DoesNotExistError, ImportError):
		return False
	return os.path.exists(path)


def is_classic_layout(format_data) -> bool:
	if not format_data:
		return False
	if isinstance(format_data, str):
		try:
			format_data = json.loads(format_data)
		except ValueError:
			return False
	return isinstance(format_data, list)


def uses_beta_renderer(print_format) -> bool:
	"""Whether a format renders through the builder renderer: only formats flagged
	`print_format_builder_beta`; classic layouts keep the standard template."""
	if not print_format:
		return False
	if print_format.get("custom_format") or print_format.get("raw_printing"):
		return False
	if print_format.get("print_designer"):
		return False
	if not print_format.get("print_format_builder_beta"):
		return False
	return print_format.get("standard") != "Yes" or bool(print_format.get("format_data"))


def uses_legacy_weasyprint(print_format) -> bool:
	"""A builder format still stored on WeasyPrint renders through the frozen v16
	generator and templates until it is switched to Chrome or Typst."""
	return uses_beta_renderer(print_format) and print_format.get("pdf_generator") == "WeasyPrint"


def convert_classic_to_beta(format_data, meta, print_format=None) -> tuple[dict, list]:
	"""Convert a classic print-format-builder layout (flat JSON array) to the
	beta builder's nested layout object.

	Returns (layout, dropped) where dropped lists fieldnames that no longer
	exist in the doctype and were left out of the converted layout."""
	dropped = []
	show_section_headings = cint(print_format.get("show_section_headings")) if print_format else 0
	line_breaks = cint(print_format.get("line_breaks")) if print_format else 0

	layout = {
		"sections": [],
		"header": {"columns": [{"label": "", "fields": []}]},
		"footer": {"columns": [{"label": "", "fields": []}]},
	}

	data = [frappe._dict(df) for df in (format_data or []) if isinstance(df, dict)]

	if data and data[0].fieldname == "print_heading_template":
		head = data.pop(0)
		if head.options:
			layout["header"]["columns"][0]["fields"].append(
				{
					"label": "",
					"fieldname": "print_heading_template",
					"fieldtype": "HTML",
					"html": head.options,
					"custom": 1,
				}
			)

	state = frappe._dict(section=None, column=None, html_count=0, skip=False)

	def new_section(label=""):
		state.section = {"label": label or "", "columns": []}
		if label and not show_section_headings:
			state.section["show_label"] = "hide"
		state.column = None
		layout["sections"].append(state.section)

	def new_column():
		if not state.section:
			new_section()
		state.column = {"label": "", "fields": []}
		state.section["columns"].append(state.column)

	def add_field(field):
		if not state.column:
			new_column()
		state.column["fields"].append(field)

	for df in data:
		if df.fieldtype in ("Section Break", "Tab Break"):
			state.skip = bool(cint(df.print_hide))
			if state.skip:
				state.section = state.column = None
			else:
				new_section(df.label if df.fieldtype == "Section Break" else "")
		elif state.skip:
			continue
		elif df.fieldtype == "Column Break":
			new_column()
		elif df.fieldtype == "HTML":
			state.html_count += 1
			add_field(
				{
					"label": df.label or "Custom HTML",
					"fieldname": f"custom_html_{state.html_count}",
					"fieldtype": "HTML",
					"html": df.options or "",
					"custom": 1,
				}
			)
		elif df.fieldname:
			if cint(df.print_hide):
				continue
			meta_df = meta.get_field(df.fieldname)
			if not meta_df:
				dropped.append(df.fieldname)
				continue
			field = {
				"label": df.label or meta_df.label or meta_df.fieldname,
				"fieldname": meta_df.fieldname,
				"fieldtype": meta_df.fieldtype,
				"options": meta_df.options,
			}
			if df.align:
				field["align"] = df.align
			if cint(df.nolabel):
				field["show_label"] = "hide"
			if meta_df.fieldtype == "Table":
				field["show_label"] = "hide"
				field["table_columns"] = convert_table_columns(df, meta_df, dropped)
			add_field(field)

	layout["sections"] = [
		section for section in layout["sections"] if any(column["fields"] for column in section["columns"])
	]
	if not data and not layout["sections"]:
		layout["sections"] = create_default_layout(meta)["sections"]

	for section in layout["sections"][1:]:
		section["margin"] = {"top": CONVERTED_SECTION_GAP_PX, "right": 0, "bottom": 0, "left": 0}

	if line_breaks:
		for section in layout["sections"][1:]:
			section["columns"][0]["fields"].insert(
				0, {"label": "", "fieldname": "divider", "fieldtype": "Divider", "custom": 1}
			)

	return layout, dropped


def convert_table_columns(df, meta_df, dropped) -> list:
	child_meta = frappe.get_meta(meta_df.options)
	columns = [
		{
			"label": "Sr",
			"fieldname": "idx",
			"fieldtype": "Int",
			"options": None,
			"width": DEFAULT_COLUMN_WIDTH_PCT,
		}
	]

	if df.get("visible_columns"):
		for col in df.visible_columns:
			col = frappe._dict(col)
			if cint(col.print_hide):
				continue
			child_df = child_meta.get_field(col.fieldname)
			if not child_df:
				dropped.append(f"{meta_df.fieldname}.{col.fieldname}")
				continue
			columns.append(
				{
					"label": child_df.label or child_df.fieldname,
					"fieldname": child_df.fieldname,
					"fieldtype": child_df.fieldtype,
					"options": child_df.options,
					"width": parse_print_width(col.print_width),
				}
			)
	else:
		child_fields = [
			child_df
			for child_df in child_meta.fields
			if child_df.fieldtype not in ("Section Break", "Column Break", "Tab Break")
			and not cint(child_df.print_hide)
		]
		if len(child_fields) > MAX_DEFAULT_TABLE_COLUMNS:
			# a wide child table keeps what its author marked essential: the list-view
			# and mandatory columns, plus the rich-text description
			child_fields = [
				df
				for df in child_fields
				if cint(df.in_list_view) or cint(df.reqd) or df.fieldtype == "Text Editor"
			] or child_fields
		for child_df in child_fields:
			columns.append(
				{
					"label": child_df.label or child_df.fieldname,
					"fieldname": child_df.fieldname,
					"fieldtype": child_df.fieldtype,
					"options": child_df.options,
					"width": parse_print_width(child_df.width),
				}
			)

	return distribute_widths(columns)


def parse_print_width(print_width) -> float | None:
	if not print_width:
		return None
	print_width = str(print_width).strip()
	try:
		if print_width.endswith("%"):
			return float(print_width[:-1])
		if print_width.endswith("px"):
			return round(float(print_width[:-2]) / ASSUMED_BODY_WIDTH_PX * 100, 2)
		return float(print_width)
	except ValueError:
		return None


def distribute_widths(columns) -> list:
	for col in columns:
		if (col.get("width") or 0) < 0:
			col["width"] = None
	unsized = [col for col in columns if not col["width"]]
	assigned = sum(col["width"] for col in columns if col["width"])
	if unsized:
		share = max(100 - assigned, DEFAULT_COLUMN_WIDTH_PCT * len(unsized)) / len(unsized)
		for col in unsized:
			col["width"] = round(share, 2)
	total = sum(col["width"] for col in columns)
	if total > 100:
		for col in columns:
			col["width"] = round(col["width"] / total * 100, 2)
	return columns


def missing_numeric_defaults(values) -> dict:
	"""DocType defaults for numeric fields left unset. Margins only when all four are."""
	meta = frappe.get_meta("Print Format")
	fields = list(NUMERIC_DEFAULT_FIELDS)
	if any(values.get(f) for f in MARGIN_FIELDS):
		fields = [f for f in fields if f not in MARGIN_FIELDS]
	return {f: flt(meta.get_field(f).default) for f in fields if not values.get(f)}


def convert_print_format(doc):
	"""Convert a classic Print Format document to beta in place (does not save).

	Keeps the original classic array in `classic_format_data` so the conversion
	is reversible and re-runnable."""
	if doc.custom_format or doc.raw_printing or renders_from_file(doc):
		return
	backup = parse_classic_backup(doc.classic_format_data)
	if backup:
		format_data = backup["format_data"]
		fields = backup["fields"]
	else:
		try:
			format_data = json.loads(doc.format_data) if doc.format_data else []
		except ValueError:
			return
		fields = {f: doc.get(f) for f in CONVERTED_FIELDS}
	if not isinstance(format_data, list):
		return

	meta = frappe.get_meta(doc.doc_type)
	if format_data:
		layout, dropped = convert_classic_to_beta(format_data, meta, doc)
		repair_layout(layout)
	else:
		layout, dropped = create_default_layout(meta), []
	doc.classic_format_data = json.dumps({"format_data": format_data, "fields": fields}, indent=1)
	doc.format_data = json.dumps(layout, indent=1)
	doc.print_format_builder = 0
	doc.print_format_builder_beta = 1
	for fieldname, value in missing_numeric_defaults(doc).items():
		doc.set(fieldname, value)
	doc.pdf_generator = "chrome"
	if not doc.page_number or doc.page_number == "Hide":
		doc.page_number = "Bottom Center"
	return dropped


def conversion_values(doc) -> dict:
	return {f: doc.get(f) for f in CONVERSION_VALUE_FIELDS}


def parse_classic_backup(classic_format_data) -> dict | None:
	"""The `{"format_data": [...], "fields": {...}}` backup `convert_print_format` writes."""
	if not classic_format_data:
		return None
	try:
		backup = json.loads(classic_format_data)
	except ValueError:
		return None
	if isinstance(backup, list):
		return {"format_data": backup, "fields": {}}
	if not isinstance(backup, dict) or not isinstance(backup.get("format_data"), list):
		return None
	return {"format_data": backup["format_data"], "fields": backup.get("fields") or {}}


def restore_classic_format(doc) -> bool:
	"""Reverse `convert_print_format` in place from the `classic_format_data` backup."""
	backup = parse_classic_backup(doc.classic_format_data)
	if not backup:
		return False
	doc.format_data = json.dumps(backup["format_data"], indent=1)
	for fieldname in CONVERTED_FIELDS:
		if fieldname in backup["fields"]:
			doc.set(fieldname, backup["fields"][fieldname])
	doc.classic_format_data = None
	doc.print_format_builder = 1
	doc.print_format_builder_beta = 0
	return True


def repair_layout(layout) -> bool:
	"""Give a converted layout the defaults the builder expects: a full-width serial
	column and spacing between sections."""
	if not isinstance(layout, dict):
		return False
	changed = False
	zones = [layout.get("header"), layout.get("footer"), *(layout.get("sections") or [])]
	for zone in zones:
		for column in (zone or {}).get("columns", []):
			for field in column.get("fields", []):
				if widen_serial_column(field.get("table_columns")):
					changed = True
	if add_section_spacing(layout):
		changed = True
	return changed


def add_section_spacing(layout) -> bool:
	"""Skipped once any section carries spacing: someone has been in the builder since."""
	sections = [s for s in (layout.get("sections") or [])[1:] if isinstance(s, dict)]
	if any(s.get("margin") or s.get("padding") for s in sections):
		return False
	for section in sections:
		section["margin"] = {"top": CONVERTED_SECTION_GAP_PX, "right": 0, "bottom": 0, "left": 0}
	return bool(sections)


def widen_serial_column(table_columns) -> bool:
	if not table_columns:
		return False
	sr = table_columns[0]
	width = sr.get("width")
	if sr.get("fieldname") != "idx" or not width or width >= DEFAULT_COLUMN_WIDTH_PCT:
		return False
	others = sum(col.get("width") or 0 for col in table_columns[1:])
	if others:
		factor = (others - (DEFAULT_COLUMN_WIDTH_PCT - width)) / others
		for col in table_columns[1:]:
			if col.get("width"):
				col["width"] = round(col["width"] * factor, 2)
	sr["width"] = DEFAULT_COLUMN_WIDTH_PCT
	return True


def is_printable_docfield(df) -> bool:
	return df.fieldtype not in no_value_fields or df.fieldtype in ("Table", "Table MultiSelect")


def create_default_layout(meta) -> dict:
	"""Build the new builder's default layout for a doctype from its meta.

	Mirrors `create_default_layout()` in the JS builder so the Standard (no custom
	format) print of every doctype renders through the new renderer."""
	layout = {
		"header": {
			"columns": [
				{
					"label": "",
					"fields": [
						{
							"label": "",
							"fieldname": "print_heading_template",
							"fieldtype": "HTML",
							"html": DEFAULT_PRINT_HEADING,
							"custom": 1,
						}
					],
				}
			]
		},
		"footer": {"columns": [{"label": "", "fields": []}]},
		"sections": [],
	}
	state = frappe._dict(section=None, column=None, skip=False)

	def new_section(df=None):
		state.section = {"label": (df.label if df else "") or "", "columns": [], "has_fields": False}
		state.column = None
		layout["sections"].append(state.section)

	def new_column(df=None):
		if not state.section:
			new_section()
		state.column = {"label": (df.label if df else "") or "", "fields": []}
		state.section["columns"].append(state.column)

	for df in meta.fields:
		if not df.fieldname:
			continue
		if df.fieldtype == "Section Break":
			state.skip = bool(cint(df.print_hide))
			if state.skip:
				state.section = state.column = None
			else:
				new_section(df)
		elif state.skip:
			continue
		elif df.fieldtype == "Column Break":
			new_column(df)
		elif df.label and is_printable_docfield(df):
			if not state.column:
				new_column()
			if cint(df.print_hide):
				continue
			field = {
				"label": df.label,
				"fieldname": df.fieldname,
				"fieldtype": df.fieldtype,
				"options": df.options,
			}
			if df.fieldtype == "Table":
				field["show_label"] = "hide"
				field["table_columns"] = convert_table_columns(frappe._dict(fieldname=df.fieldname), df, [])
			state.column["fields"].append(field)
			state.section["has_fields"] = True

	layout["sections"] = [s for s in layout["sections"] if s.get("has_fields")]
	for section in layout["sections"]:
		section.pop("has_fields", None)
	return layout


@frappe.whitelist()
def get_beta_layout(print_format: str) -> dict:
	"""Convert a classic format's layout for the print format builder (read-only,
	the conversion is persisted only when the user saves)."""
	doc = frappe.get_doc("Print Format", print_format)
	doc.check_permission("write")

	dropped = convert_print_format(doc)
	if dropped is None:
		frappe.throw(frappe._("{0} is not a classic print format").format(print_format))
	return {
		"layout": json.loads(doc.format_data),
		"dropped": dropped,
		"values": conversion_values(doc),
	}
