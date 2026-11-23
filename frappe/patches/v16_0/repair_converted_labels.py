import html
import json
import re

import frappe
from frappe.printing.layout import iter_fields, iter_zones

HTML_ENTITY = re.compile(r"&(?:#\d+|#x[\da-f]+|[a-z][a-z\d]*);", re.IGNORECASE)
CUSTOM_HTML_LABEL_END = re.compile(r":(?:&amp;nbsp;)+</span>")


def execute():
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
