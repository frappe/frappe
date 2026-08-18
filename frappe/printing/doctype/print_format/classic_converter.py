# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.utils import cint, flt

ASSUMED_BODY_WIDTH_PX = 750
DEFAULT_COLUMN_WIDTH_PCT = 10
# classic wrapped text and table blocks in `padding: 10px 0px`; the beta renderer
# has no such default, so converted sections carry the gap explicitly
CONVERTED_SECTION_GAP_PX = 10
MARGIN_FIELDS = ("margin_top", "margin_bottom", "margin_left", "margin_right")
NUMERIC_DEFAULT_FIELDS = ("font_size", *MARGIN_FIELDS)

DEFAULT_PRINT_HEADING = (
	'{%- set heading = doc.get("select_print_heading") or doc.get("print_heading") or doc.doctype -%}'
	'{%- set sub_heading = doc.get("sub_heading") or doc.name -%}'
	'<div class="print-heading"><h2><div>{{ _(heading) }}</div>'
	'<small class="sub-heading">{{ _(sub_heading|string) }}</small></h2></div>'
)


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
	if not print_format:
		return False
	if print_format.get("custom_format") or print_format.get("raw_printing"):
		return False
	# Print Designer formats carry their own format_data schema and renderer;
	# also covers rows whose beta flag was flipped wrongly on insert
	if print_format.get("print_designer"):
		return False
	if print_format.get("print_format_builder_beta"):
		# a standard format with no layout is a file-based Jinja format whose
		# flag was set wrongly on insert — the beta renderer has nothing to draw
		return print_format.get("standard") != "Yes" or bool(print_format.get("format_data"))
	return is_classic_layout(print_format.get("format_data"))


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
		if df.fieldtype == "Section Break":
			state.skip = bool(cint(df.print_hide))
			if state.skip:
				state.section = state.column = None
			else:
				new_section(df.label)
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
	if doc.custom_format or doc.raw_printing:
		return
	source = doc.classic_format_data or doc.format_data
	if not source:
		return
	try:
		format_data = json.loads(source)
	except ValueError:
		return
	if not isinstance(format_data, list):
		return

	layout, dropped = convert_classic_to_beta(format_data, frappe.get_meta(doc.doc_type), doc)
	doc.classic_format_data = json.dumps(format_data, indent=1)
	doc.format_data = json.dumps(layout, indent=1)
	doc.print_format_builder = 0
	doc.print_format_builder_beta = 1
	for fieldname, value in missing_numeric_defaults(doc).items():
		doc.set(fieldname, value)
	doc.pdf_generator = "chrome"
	if not doc.page_number or doc.page_number == "Hide":
		doc.page_number = "Bottom Center"
	return dropped


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
		elif df.label:
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


def get_default_print_format(doctype: str):
	"""Return an unsaved "Standard" beta Print Format for a doctype so the default
	(no custom format) print renders through the new renderer."""
	pf = frappe.new_doc("Print Format")
	pf.name = "Standard"
	pf.doc_type = doctype
	pf.standard = "Yes"
	pf.print_format_builder_beta = 1
	pf.pdf_generator = "chrome"
	pf.format_data = json.dumps(create_default_layout(frappe.get_meta(doctype)))
	return pf


@frappe.whitelist()
def get_beta_layout(print_format: str) -> dict:
	"""Convert a classic format's layout for the print format builder (read-only,
	the conversion is persisted only when the user saves)."""
	doc = frappe.get_doc("Print Format", print_format)
	doc.check_permission("write")

	not_classic = frappe._("{0} is not a classic print format").format(print_format)
	if doc.custom_format or doc.raw_printing or not doc.format_data:
		frappe.throw(not_classic)
	try:
		format_data = json.loads(doc.format_data)
	except ValueError:
		frappe.throw(not_classic)
	if not isinstance(format_data, list):
		frappe.throw(not_classic)

	layout, dropped = convert_classic_to_beta(format_data, frappe.get_meta(doc.doc_type), doc)
	return {"layout": layout, "dropped": dropped, "classic_format_data": doc.format_data}


def migrate_all_classic_formats():
	"""Convert every classic builder format on the site — standard (app-shipped) and
	custom alike. Non-classic formats are skipped by convert_print_format. Standard
	formats are written straight to the db so the conversion is not exported back to
	the app's source files; the render-time shim re-converts any that a later app
	sync reverts to classic. Idempotent: re-converts from `classic_format_data`."""
	names = frappe.get_all(
		"Print Format",
		filters={"custom_format": 0, "raw_printing": 0, "print_format_builder_beta": 0},
		pluck="name",
	)
	report = {}
	for name in names:
		try:
			doc = frappe.get_doc("Print Format", name)
			dropped = convert_print_format(doc)
			if dropped is None:
				continue
			if doc.standard == "Yes":
				frappe.db.set_value(
					"Print Format",
					name,
					{
						"format_data": doc.format_data,
						"classic_format_data": doc.classic_format_data,
						"print_format_builder": 0,
						"print_format_builder_beta": 1,
						"pdf_generator": doc.pdf_generator,
						"page_number": doc.page_number,
						**{f: doc.get(f) for f in NUMERIC_DEFAULT_FIELDS},
					},
					update_modified=False,
				)
			else:
				doc.save(ignore_permissions=True)
			report[name] = dropped
		except Exception:
			frappe.log_error(title=f"Print Format conversion failed: {name}")
	return report
