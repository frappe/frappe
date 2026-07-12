# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.utils import cint

ASSUMED_BODY_WIDTH_PX = 750
DEFAULT_COLUMN_WIDTH_PCT = 10


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
	if not print_format or not print_format.get("format_data"):
		return False
	if print_format.get("custom_format") or print_format.get("raw_printing"):
		return False
	return bool(print_format.get("print_format_builder_beta")) or is_classic_layout(
		print_format.get("format_data")
	)


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

	data = [frappe._dict(df) for df in (format_data or [])]

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

	state = frappe._dict(section=None, column=None, html_count=0)

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
		if df.fieldtype == "Section Break":
			new_section(df.label)
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
			"width": parse_print_width("40px"),
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
		for child_df in child_meta.fields:
			if child_df.fieldtype in ("Section Break", "Column Break") or cint(child_df.print_hide):
				continue
			columns.append(
				{
					"label": child_df.label or child_df.fieldname,
					"fieldname": child_df.fieldname,
					"fieldtype": child_df.fieldtype,
					"options": child_df.options,
					"width": None,
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


def convert_print_format(doc):
	"""Convert a classic Print Format document to beta in place (does not save).

	Keeps the original classic array in `classic_format_data` so the conversion
	is reversible and re-runnable."""
	if doc.custom_format or doc.raw_printing:
		return
	source = doc.classic_format_data or doc.format_data
	if not source:
		return
	format_data = json.loads(source)
	if not isinstance(format_data, list):
		return

	layout, dropped = convert_classic_to_beta(format_data, frappe.get_meta(doc.doc_type), doc)
	doc.classic_format_data = json.dumps(format_data, indent=1)
	doc.format_data = json.dumps(layout, indent=1)
	doc.print_format_builder = 0
	doc.print_format_builder_beta = 1
	doc.pdf_generator = "chrome"
	if not doc.page_number or doc.page_number == "Hide":
		doc.page_number = "Bottom Center"
	return dropped


@frappe.whitelist()
def get_beta_layout(print_format: str) -> dict:
	"""Convert a classic format's layout for the print format builder (read-only,
	the conversion is persisted only when the user saves)."""
	doc = frappe.get_doc("Print Format", print_format)
	doc.check_permission("write")

	format_data = json.loads(doc.format_data)
	if not isinstance(format_data, list):
		frappe.throw(frappe._("{0} is not a classic print format").format(print_format))

	layout, dropped = convert_classic_to_beta(format_data, frappe.get_meta(doc.doc_type), doc)
	return {"layout": layout, "dropped": dropped, "classic_format_data": doc.format_data}


def migrate_all_classic_formats():
	"""Convert every non-standard classic format on the site. Idempotent: already
	converted formats are re-converted from their `classic_format_data` backup."""
	names = frappe.get_all(
		"Print Format",
		filters={"standard": "No"},
		or_filters=[
			["print_format_builder", "=", 1],
			["classic_format_data", "is", "set"],
		],
		pluck="name",
	)
	report = {}
	for name in names:
		doc = frappe.get_doc("Print Format", name)
		dropped = convert_print_format(doc)
		if dropped is None:
			continue
		doc.save(ignore_permissions=True)
		report[name] = dropped
	return report
