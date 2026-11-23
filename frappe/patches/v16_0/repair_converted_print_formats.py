import html
import json
import re

import frappe
from frappe.printing.doctype.print_format.classic_converter import (
	CONVERTED_SECTION_GAP_PX,
	DEFAULT_COLUMN_WIDTH_PCT,
	NUMERIC_DEFAULT_FIELDS,
	missing_numeric_defaults,
)
from frappe.printing.layout import iter_fields, iter_zones
from frappe.utils.print_format_generator import layout_page_settings

HTML_ENTITY = re.compile(r"&(?:#\d+|#x[\da-f]+|[a-z][a-z\d]*);", re.IGNORECASE)
CUSTOM_HTML_LABEL_END = re.compile(r":(?:&amp;nbsp;)+</span>")


def execute():
	"""Repair formats converted before the converter fixes: numeric fields left at 0,
	narrow serial columns, sections with no spacing, paper size dropped. Nothing else
	is touched."""
	names = frappe.get_all(
		"Print Format",
		filters={"print_format_builder_beta": 1, "classic_format_data": ("is", "set")},
		pluck="name",
	)
	fields = ["format_data", "paper_size", "paper_width", "paper_height", *NUMERIC_DEFAULT_FIELDS]
	for name in names:
		row = frappe.db.get_value("Print Format", name, fields, as_dict=True)
		values = missing_numeric_defaults(row)
		repaired = repair_layout(row.format_data, row.paper_size, row.paper_width, row.paper_height)
		if repaired:
			values["format_data"] = repaired
		if values:
			frappe.db.set_value("Print Format", name, values, update_modified=False)


def repair_converted_labels():
	"""Print Designer formats converted before the converter decoded labels still store
	its entities and print them literally. A conversion keeps its design on the record;
	without the app's fields, its own `In Words :&nbsp;` label is the only mark left."""
	or_filters = [["format_data", "like", '%:&nbsp;"%'], ["format_data", "like", "%:&amp;nbsp;%"]]
	if frappe.get_meta("Print Format").has_field("print_designer_body"):
		or_filters.append(["print_designer_body", "is", "set"])
	names = frappe.get_all(
		"Print Format",
		filters={"print_format_builder_beta": 1, "classic_format_data": ("is", "not set")},
		or_filters=or_filters,
		pluck="name",
	)
	for name in names:
		row = frappe.db.get_value("Print Format", name, ["format_data", "draft_data"], as_dict=True)
		values = {}
		if repaired := decode_labels(row.format_data):
			values["format_data"] = repaired
		if repaired_draft := decode_draft_labels(row.draft_data):
			values["draft_data"] = repaired_draft
		if values:
			frappe.db.set_value("Print Format", name, values, update_modified=False)


def decode_draft_labels(draft_data):
	try:
		draft = json.loads(draft_data)
	except (TypeError, ValueError):
		return None
	if not isinstance(draft, dict):
		return None

	repaired = decode_labels(draft.get("format_data"))
	return frappe.as_json({**draft, "format_data": repaired}) if repaired else None


def decode_labels(format_data):
	try:
		layout = json.loads(format_data)
	except (TypeError, ValueError):
		return None
	if not isinstance(layout, dict):
		return None

	changed = False
	for _where, zone in iter_zones(layout):
		for field in iter_fields(zone):
			stored_label = field.get("label")
			label = decode_entities(stored_label)
			if label != stored_label:
				field["label"] = label.strip().rstrip(":").strip()
				changed = True
			custom_html = field.get("html")
			if isinstance(custom_html, str):
				decoded_html = CUSTOM_HTML_LABEL_END.sub(
					lambda label_end: label_end.group().replace("&amp;nbsp;", "\xa0"), custom_html
				)
				if decoded_html != custom_html:
					field["html"] = decoded_html
					changed = True
			table_columns = field.get("table_columns")
			for table_column in table_columns if isinstance(table_columns, list) else []:
				if not isinstance(table_column, dict):
					continue
				label = decode_entities(table_column.get("label"))
				if label != table_column.get("label"):
					table_column["label"] = label
					changed = True
	return json.dumps(layout, indent=1) if changed else None


def decode_entities(label):
	if not isinstance(label, str):
		return label
	decoded = HTML_ENTITY.sub(lambda entity: html.unescape(entity.group()), label)
	return label if HTML_ENTITY.search(decoded) else decoded


def repair_layout(format_data, paper_size, paper_width=None, paper_height=None):
	try:
		layout = json.loads(format_data)
	except (TypeError, ValueError):
		return None
	if not isinstance(layout, dict):
		return None

	changed = False
	zones = [layout.get("header"), layout.get("footer"), *layout.get("sections", [])]
	for zone in zones:
		for column in (zone or {}).get("columns", []):
			for field in column.get("fields", []):
				if widen_serial_column(field.get("table_columns")):
					changed = True
	if add_section_spacing(layout):
		changed = True
	if add_page_size(layout, paper_size, paper_width, paper_height):
		changed = True
	return json.dumps(layout, indent=1) if changed else None


def add_page_size(layout, paper_size, paper_width=None, paper_height=None):
	page = layout.get("page") or {}
	size = {"size": paper_size}
	if paper_size == "Custom":
		size.update(width=paper_width, height=paper_height)
	if page.get("size") or not layout_page_settings({"page": size}):
		return False
	layout["page"] = {**page, **size}
	return True


def add_section_spacing(layout):
	"""Classic carried the gap between blocks in its own markup, so the conversion
	never stored one and converted sections print flush against each other. The
	first section sits under the header, which already has its own gap.

	Skipped entirely once any section carries spacing: that means someone has been
	in the builder since the conversion, and sections they left unspaced were left
	that way on purpose."""
	sections = [s for s in (layout.get("sections") or [])[1:] if isinstance(s, dict)]
	if any(s.get("margin") or s.get("padding") for s in sections):
		return False

	for section in sections:
		section["margin"] = {"top": CONVERTED_SECTION_GAP_PX, "right": 0, "bottom": 0, "left": 0}
	return bool(sections)


def widen_serial_column(table_columns):
	if not table_columns:
		return False
	sr = table_columns[0]
	width = sr.get("width")
	if sr.get("fieldname") != "idx" or not width or width >= DEFAULT_COLUMN_WIDTH_PCT:
		return False

	# widen Sr to the default and shrink the other columns by the difference,
	# keeping the total unchanged
	others = sum(col.get("width") or 0 for col in table_columns[1:])
	if others:
		factor = (others - (DEFAULT_COLUMN_WIDTH_PCT - width)) / others
		for col in table_columns[1:]:
			if col.get("width"):
				col["width"] = round(col["width"] * factor, 2)
	sr["width"] = DEFAULT_COLUMN_WIDTH_PCT
	return True
